"""The Vercel deploy surface: ``vercel.json``, ``api/index.py`` and the files they promise.

Nothing else in this repository touches either file. Measured 2026-11-09: no workflow under
``.github/`` mentions ``vercel`` or ``api/index``, and no test imported the entry point, so the
only thing that had ever exercised the deploy surface was a Vercel build - a third-party check
row, optional in our merge gate, which a fork pull request cannot even produce until the
repository owner authorises that one pull request by hand.

Two defects are recorded in CLAUDE.md as having reached production through that hole, and both
are config-only, so nothing in ``src/`` changes and no test of the package could have seen
either one:

* a missing ``installCommand``, which makes Vercel install from ``pyproject.toml`` with no
  extras, so every request is a 500 ``FUNCTION_INVOCATION_FAILED`` with
  ``ModuleNotFoundError: fastapi``;
* a catch-all rewrite to ``/api/index``, which makes every request a 404, because the Vercel
  Python runtime already routes every path to the ASGI app itself.

The job that runs this module builds its environment from ``installCommand`` itself, with
Vercel's no-``installCommand`` default as the fallback, so deleting that line fails the job with
the same ``ModuleNotFoundError`` it would put in production rather than with a reading of the
file. ``UNIPROTPTMPY_REQUIRE_DEPLOY_SURFACE=1`` is what turns that into a failure: without it
the two import tests skip, which is what has to happen in the ``no-extras`` job and in a plain
``uv sync`` checkout, and a skip is how this whole class of defect stays invisible.

One test here is not about the deploy surface but about this module's own apparatus.
``vercel.json`` declares no rewrites, routes or redirects - on any of the three packages - so
``test_no_rule_in_vercel_json_can_swallow_every_path`` iterates over nothing and would pass with a
constant matcher, which is this module's own defect class turned on itself.
``test_the_catch_all_translator_recognises_a_catch_all`` is what keeps that matcher honest while
the config stays empty, and it has to stay even if the loop one day has rules to walk.

Reference form for the sister vocabulary packages (psimodpy, unimodpy), which have the same two
files and the same hole: everything package-specific is in the constants below, and every other
name is read out of ``vercel.json``, the pyproject or the source.
"""

from __future__ import annotations

import ast
import glob as globlib
import importlib
import importlib.util
import os
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
PACKAGE = "uniprotptmpy"
SRC = ROOT / "src"
ENTRY = "api/index.py"
# The extra that supplies what the entry point's import chain needs. Checked against the
# chain's actual imports and against the pyproject, so a wrong value here cannot be quiet.
ENTRY_EXTRA = "server"
REQUIRE = "UNIPROTPTMPY_REQUIRE_DEPLOY_SURFACE"
JOB = "deploy-surface"
WORKFLOW = ".github/workflows/ci.yml"
# Files the running app reads from disk, by the path it reads them at. `includeFiles` is what
# puts them in the function bundle, and `test_the_app_finds_the_file_include_files_promises`
# proves the app looks where the glob delivers rather than taking this list on trust.
RUNTIME_FILES = ("docs/index.html",)

# What Vercel does when `installCommand` is absent: install the project with no extras.
VERCEL_DEFAULT_INSTALL = "uv pip install ."

# Paths a catch-all rule would swallow. The app serves all of them (`server/app.py`), so a rule
# matching every one of them is the 404 defect whatever its destination.
PROBES = ("/", "/data.json", "/api/health", "/api/entries/PTM-0253", "/mcp", "/openapi.json")

# Measured 2026-11-09 on this tree: the walk below reaches api/index.py plus uniprotptmpy,
# uniprotptmpy.server.app, .dashboard and .models, and finds fastapi, mcp and pydantic. Floors
# rather than equalities, because an import added under server/ is not this module's business -
# but a walk that collects nothing would otherwise make every assertion here vacuous.
MIN_ENTRY_MODULES = 5
MIN_ENTRY_ROOTS = 3


def vercel() -> dict:
    """``vercel.json`` as parsed JSON, which is the only authority on the deploy surface."""
    import json

    text = (ROOT / "vercel.json").read_text(encoding="utf-8")
    config = json.loads(text)
    assert isinstance(config, dict), f"vercel.json is {type(config).__name__}, not an object"
    return config


def function_config() -> dict:
    """The ``functions`` entry for the entry point."""
    functions = vercel().get("functions")
    assert isinstance(functions, dict) and functions, "vercel.json declares no `functions`"
    assert ENTRY in functions, f"vercel.json declares functions {sorted(functions)}, not {ENTRY!r}"
    config = functions[ENTRY]
    assert isinstance(config, dict), f"functions[{ENTRY!r}] is {type(config).__name__}, not an object"
    return config


def include_globs() -> tuple[str, ...]:
    """``includeFiles`` as a tuple; Vercel accepts a string or a list of strings."""
    value = function_config().get("includeFiles")
    assert value is not None, (
        f"functions[{ENTRY!r}] declares no includeFiles, so the function bundle carries no "
        f"{RUNTIME_FILES} and the dashboard 404s in production"
    )
    globs = (value,) if isinstance(value, str) else tuple(value)
    assert globs and all(isinstance(glob, str) for glob in globs), f"includeFiles is {value!r}"
    return globs


def delivered_files() -> dict[str, list[Path]]:
    """Each includeFiles glob and the files it puts in the function bundle.

    `glob.glob(..., recursive=True)` and not `Path.glob`: pathlib's trailing `**` matched only
    directories up to 3.12 and matches files as well from 3.13, so `docs/**` resolved to no
    files at all on 3.12. Measured on PR #72, where `test (ubuntu-latest, 3.12)` and `lowest`
    failed on exactly that while 3.13, 3.14 and the workspace venv all passed - the two
    assertions below were reading the Python version rather than the deploy surface. Vercel's
    own matcher counts files, which is what this one does on every version.
    """
    return {
        pattern: sorted(
            ROOT / name for name in globlib.glob(pattern, root_dir=ROOT, recursive=True) if (ROOT / name).is_file()
        )
        for pattern in include_globs()
    }


def module_source(dotted: str) -> Path | None:
    """The source file for a module of this package, or None for anything else."""
    parts = dotted.split(".")
    if parts[0] != PACKAGE:
        return None
    base = SRC.joinpath(*parts)
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    pytest.fail(f"{dotted} is imported but has no source under {SRC}")


def module_scope_imports(path: Path) -> list[str]:
    """Dotted names `path` imports at module scope.

    Module scope means ``tree.body`` and not ``ast.walk``: an import under ``if TYPE_CHECKING:``
    or inside a function never runs at import time, so it cannot be what Vercel has to install.
    """
    names: list[str] = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, (
                f"{path} uses a relative import at module scope, which this walk cannot resolve; "
                f"teach it or make the import absolute"
            )
            assert node.module is not None
            names.append(node.module)
    return names


def entry_chain() -> tuple[set[str], set[str]]:
    """Every module reachable from the entry point at import time, and its third-party roots.

    This is exactly the set Vercel has to be able to import, read off the source rather than by
    importing, so it answers the same in an environment that has none of it.
    """
    entry = ROOT / ENTRY
    assert entry.is_file(), f"{ENTRY} does not exist, so Vercel has no function to serve"
    modules = {ENTRY}
    roots: set[str] = set()
    queue = [entry]
    while queue:
        for dotted in module_scope_imports(queue.pop()):
            root = dotted.split(".")[0]
            if root in sys.stdlib_module_names or dotted == "__future__":
                continue
            if root != PACKAGE:
                roots.add(root)
                continue
            if dotted in modules:
                continue
            modules.add(dotted)
            source = module_source(dotted)
            if source is not None:
                queue.append(source)
    return modules, roots


def declared_extras() -> dict[str, set[str]]:
    """Each declared extra and the distribution names it requires."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras: dict[str, set[str]] = {}
    for extra, requirements in pyproject["project"]["optional-dependencies"].items():
        names = set()
        for requirement in requirements:
            matched = re.match(r"^(?P<name>[A-Za-z0-9._-]+)", requirement.strip())
            assert matched is not None, f"cannot parse requirement {requirement!r}"
            names.add(matched["name"])
        extras[extra] = names
    assert extras, "the pyproject declares no optional dependencies"
    return extras


def missing_roots() -> tuple[str, ...]:
    """The entry point's third-party roots that this environment cannot locate."""
    missing = []
    for root in sorted(entry_chain()[1]):
        try:
            found = importlib.util.find_spec(root) is not None
        except ModuleNotFoundError:
            found = False
        if not found:
            missing.append(root)
    return tuple(missing)


def require_or_skip(missing: tuple[str, ...] | None = None) -> None:
    """Skip when the entry point cannot be imported here, or fail when a job required it.

    Two callers, two needs: `uv sync` with no extras and CI's `no-extras` job must skip, while
    the `deploy-surface` job installs what vercel.json installs and so must fail. The env var is
    the whole difference, and `test_the_gate_fails_instead_of_skipping_when_a_job_requires_it`
    is what keeps it from quietly becoming a skip in both.
    """
    missing = missing_roots() if missing is None else missing
    if not missing:
        return
    message = (
        f"the entry point {ENTRY} cannot be imported: {list(missing)} not installed. "
        f"On Vercel this is the 500 `ModuleNotFoundError` the installCommand exists to prevent."
    )
    if os.environ.get(REQUIRE) == "1":
        pytest.fail(f"{REQUIRE}=1, so this is a failure rather than a skip: {message}")
    pytest.skip(f"{message} Set {REQUIRE}=1 in a job that installs the `{ENTRY_EXTRA}` extra.")


def load_entry() -> ModuleType:
    """Import ``api/index.py`` by path, the way Vercel imports it: not as part of the package."""
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}_vercel_entry", ROOT / ENTRY)
    assert spec is not None and spec.loader is not None, f"no import spec for {ENTRY}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_matches_every_probe(source: str) -> bool:
    """Whether a Vercel `source` pattern swallows every path the app serves."""
    pattern = re.sub(r":[A-Za-z_]\w*[*+]", ".*", source)
    pattern = re.sub(r":[A-Za-z_]\w*", "[^/]+", pattern)
    try:
        compiled = re.compile(f"^{pattern}$")
    except re.error as exc:
        pytest.fail(f"cannot read the rule source {source!r} as a pattern ({exc}); teach this translator")
    return all(compiled.match(probe) for probe in PROBES)


def test_vercel_declares_exactly_one_function_and_it_is_on_disk() -> None:
    functions = vercel()["functions"]
    for name in functions:
        assert (ROOT / name).is_file(), f"vercel.json declares the function {name!r}, which does not exist"
    assert set(functions) == {ENTRY}, f"vercel.json declares {sorted(functions)}, expected [{ENTRY!r}]"


def test_the_install_command_installs_the_extra_the_entry_point_imports() -> None:
    """The 500 direction: no installCommand means no extras, and the import fails in production.

    Checked in three links rather than one, because each can be wrong on its own: the command
    has to install this project with the extra, the pyproject has to declare that extra, and the
    extra has to cover every root the entry point's import chain actually reaches.
    """
    modules, roots = entry_chain()
    assert len(modules) >= MIN_ENTRY_MODULES, f"the import walk reached only {sorted(modules)}"
    assert len(roots) >= MIN_ENTRY_ROOTS, f"the import walk found only {sorted(roots)} to install"

    command = vercel().get("installCommand")
    assert command is not None, (
        f"vercel.json declares no installCommand, so Vercel installs from pyproject.toml with no "
        f"extras ({VERCEL_DEFAULT_INSTALL!r}) and every request is a 500 with "
        f"ModuleNotFoundError for one of {sorted(roots)}"
    )
    assert re.search(r"(?<![\w./-])\.\[[^]]*\b" + re.escape(ENTRY_EXTRA) + r"\b[^]]*]", command) or re.search(
        r"--extra[= ]" + re.escape(ENTRY_EXTRA) + r"\b", command
    ), f"installCommand {command!r} does not install this project with the `{ENTRY_EXTRA}` extra"

    extras = declared_extras()
    assert ENTRY_EXTRA in extras, f"the pyproject declares extras {sorted(extras)}, not `{ENTRY_EXTRA}`"
    uncovered = roots - extras[ENTRY_EXTRA]
    assert not uncovered, (
        f"the entry point imports {sorted(uncovered)} at module scope and the `{ENTRY_EXTRA}` extra "
        f"declares only {sorted(extras[ENTRY_EXTRA])}, so installCommand cannot supply them"
    )


def test_no_rule_in_vercel_json_can_swallow_every_path() -> None:
    """The 404 direction: the Python runtime routes every path to the app, so a catch-all is wrong."""
    config = vercel()
    for key in ("rewrites", "routes", "redirects"):
        rules = config.get(key) or []
        assert isinstance(rules, list), f"vercel.json {key} is {type(rules).__name__}, not a list"
        for rule in rules:
            source = rule.get("source") or rule.get("src")
            assert source is not None, f"vercel.json {key} has a rule with no source: {rule!r}"
            assert not source_matches_every_probe(source), (
                f"vercel.json {key} rule {rule!r} matches every path the app serves ({list(PROBES)}). "
                f"The Vercel Python runtime already routes every path to {ENTRY}, so a catch-all "
                f"makes every request a 404"
            )


def test_the_catch_all_translator_recognises_a_catch_all() -> None:
    """The test above is vacuous on this tree, so check its apparatus rather than its loop.

    This vercel.json declares no rewrites, routes or redirects at all - measured, its keys are
    exactly `$schema`, `functions` and `installCommand` - so the loop in
    `test_no_rule_in_vercel_json_can_swallow_every_path` iterates over nothing and would pass
    with `source_matches_every_probe` returning a constant. Measured on the module as it landed
    in #72: with the matcher replaced by `return False`, 10 collected and 10 passed, exit 0.
    That is the whole defect class this module is about, sitting inside the module: a check that
    never attempts anything cannot see anything. Both of the shapes Vercel accepts for the
    recorded 404 defect are asserted here, against a path pattern that is not a catch-all, so
    the translator cannot rot while the config stays empty.

    Found and first fixed by the psimodpy session, which proved its own loop vacuous by mutation
    rather than by reading the config; the wording below is theirs.
    """
    for catch_all in ("/(.*)", "/:path*"):
        assert source_matches_every_probe(catch_all), (
            f"the translator does not recognise {catch_all!r} as matching every path, so the "
            f"catch-all test would pass on the 404 defect itself"
        )
    assert not source_matches_every_probe("/api/health"), (
        "the translator calls a single-path rule a catch-all, so it would reject a legitimate rule"
    )


def test_every_include_files_glob_matches_files_that_exist() -> None:
    for glob, matched in delivered_files().items():
        assert matched, (
            f"includeFiles glob {glob!r} matches no file under {ROOT}, so the function bundle carries nothing for it"
        )


def test_the_files_the_app_reads_are_the_files_include_files_delivers() -> None:
    """Both directions: the glob has to deliver a real file, and it has to be the one the app reads."""
    delivered = {path.resolve() for matched in delivered_files().values() for path in matched}
    for name in RUNTIME_FILES:
        path = ROOT / name
        assert path.is_file(), f"the app reads {name} at run time and it does not exist"
        assert path.resolve() in delivered, (
            f"the app reads {name} at run time but no includeFiles glob {list(include_globs())} "
            f"delivers it, so it is absent from the function bundle"
        )


def test_the_entry_point_exports_the_app_the_package_builds() -> None:
    require_or_skip()
    entry = load_entry()
    from uniprotptmpy.server.app import app

    assert getattr(entry, "app", None) is app, (
        f"{ENTRY} must export the same ASGI app object as {PACKAGE}.server.app; Vercel serves "
        f"whatever `app` it finds there"
    )


def test_the_app_finds_the_file_include_files_promises() -> None:
    """The app's own locator, against the file the glob delivers: the runtime half of includeFiles."""
    require_or_skip()
    # `importlib.import_module`, not `from uniprotptmpy.server import app`: the package
    # re-exports the FastAPI object under that name, so the plain import binds the app and not
    # the module, and the locator below would be looked up on the wrong object.
    app_module = importlib.import_module(f"{PACKAGE}.server.app")

    html = app_module._load_dashboard_html()
    assert html is not None, (
        f"the app found no dashboard HTML from {Path.cwd()}, so `GET /` would 404 even with "
        f"includeFiles {list(include_globs())}"
    )
    expected = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert html == expected, "the app loaded dashboard HTML that is not the file includeFiles delivers"


def test_the_gate_fails_instead_of_skipping_when_a_job_requires_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gate that silently becomes a skip reports a green suite, so watch both of its branches.

    `Skipped` is caught by hand: it is not a failure, so `pytest.raises(pytest.fail.Exception)`
    would let it through and the test announcing the gate's death would read as a skip.
    """
    monkeypatch.setenv(REQUIRE, "1")
    try:
        require_or_skip(missing=("fastapi",))
    except pytest.skip.Exception as exc:
        pytest.fail(f"the gate is dead: {REQUIRE}=1 with fastapi missing skipped instead of failing ({exc})")
    except pytest.fail.Exception as exc:
        assert "fastapi" in str(exc) and REQUIRE in str(exc), f"the failure does not say why: {exc}"
    else:
        pytest.fail(f"{REQUIRE}=1 with fastapi missing neither failed nor skipped")

    monkeypatch.delenv(REQUIRE)
    with pytest.raises(pytest.skip.Exception):
        require_or_skip(missing=("fastapi",))

    require_or_skip(missing=())


def ci_job_body(name: str) -> str:
    """One job out of ci.yml, by the two-space key rule, with comments removed.

    Comments go, or prose about a flag reads as a job that passes it - the same trap
    `tests/test_installation.py` documents. Text rather than YAML, because this module runs in
    an environment built by vercel.json's installCommand, which installs no YAML parser.
    """
    lines = (ROOT / WORKFLOW).read_text(encoding="utf-8").splitlines()
    body: list[str] = []
    current: str | None = None
    for line in lines[lines.index("jobs:") + 1 :]:
        matched = re.match(r"^ {2}(?P<name>[A-Za-z0-9_-]+):\s*$", line)
        if matched:
            current = matched["name"]
        elif current == name:
            body.append("" if line.lstrip().startswith("#") else re.sub(r"\s+#.*$", "", line))
    assert body, f"{WORKFLOW} declares no `{name}` job"
    return "\n".join(body)


def test_ci_runs_this_module_with_the_gate_set() -> None:
    """Everything above is only as good as the one job that runs it with the gate on.

    Without `REQUIRE=1` the two import tests skip, and a skipped import test is exactly the
    shape this module exists to remove, so the job that supplies the gate is itself checked.
    """
    body = ci_job_body(JOB)
    module = f"tests/{Path(__file__).name}"
    assert module in body, f"the `{JOB}` job does not run {module}"
    assert f'{REQUIRE}: "1"' in body, (
        f"the `{JOB}` job does not set {REQUIRE}=1, so the two import tests would skip there and "
        f"the job would be green without importing {ENTRY} at all"
    )
    assert VERCEL_DEFAULT_INSTALL in body, (
        f"the `{JOB}` job must fall back to {VERCEL_DEFAULT_INSTALL!r} when installCommand is "
        f"absent, because that is what Vercel itself does and what makes a deleted "
        f"installCommand fail here rather than pass"
    )


def requires_python_floor() -> str:
    """The lowest Python the pyproject allows, which is the interpreter the deploy runs on.

    Vercel's Python runtime takes the version from the pyproject rather than from whatever the
    repository tests newest. Measured on the production deployment of this repo,
    dpl_CRMj6rop5KTMjhvpmZRcELz7anqW (commit b5be642): the build log reads "Using Python 3.12
    from pyproject.toml", "Writing .python-version file with version 3.12", then "Using Python
    3.12.15 environment at: .vercel/python/.venv", with uv 0.13.5.

    A single ``>=`` clause or nothing: a specifier this cannot read fails here rather than
    letting the pin it is compared against go unchecked.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    specifier = pyproject["project"]["requires-python"]
    matched = re.fullmatch(r">=\s*(?P<floor>\d+\.\d+)(?:\.\d+)?", specifier.strip())
    assert matched is not None, (
        f"requires-python is {specifier!r} and this parser reads only a single `>=` floor, so it "
        f"cannot say which Python Vercel would pick; teach it rather than skipping the check"
    )
    return matched["floor"]


def job_python_version(name: str) -> str:
    """The one ``python-version:`` a job declares, read as text out of ci.yml."""
    body = ci_job_body(name)
    found = re.findall(r'^\s*python-version:\s*"?([^"\s]+)"?\s*$', body, flags=re.MULTILINE)
    assert len(found) == 1, (
        f"the `{name}` job declares python-version {found}, expected exactly one; this check "
        f"cannot say which interpreter the job builds on otherwise"
    )
    return found[0]


def test_the_job_builds_on_the_python_vercel_picks() -> None:
    """A job that reproduces the install on the wrong interpreter reproduces nothing.

    The pin and the pyproject floor are two places, so they are compared rather than trusted:
    a requires-python bump would otherwise leave this job building on the old interpreter and
    reporting green, which is this module's own defect class turned on itself. PR #72 is the
    worked example of why the interpreter is not a detail - `docs/**` resolved to no files on
    3.12 and to files on 3.13, so a job pinned to 3.13 would have been green on a deploy
    surface that was broken on the version the deploy uses.
    """
    floor = requires_python_floor()
    pinned = job_python_version(JOB)
    assert pinned == floor, (
        f"the `{JOB}` job builds on Python {pinned} and Vercel builds on {floor}, the "
        f"requires-python floor its build log names, so the job reproduces vercel.json's "
        f"install on an interpreter the deploy does not use"
    )
    # The second half is the pin reaching the interpreter, and it runs only in the job itself.
    # REQUIRE=1 marks the one job whose whole claim is that its environment is the deploy's;
    # `CI` keeps it out of a local run, where REQUIRE=1 is routinely set by hand inside the
    # workspace venv on a different Python and the failure would say nothing about the deploy.
    # So this half is CI-only by construction and the pin comparison above is not.
    if os.environ.get(REQUIRE) == "1" and os.environ.get("CI") == "true":
        running = ".".join(str(part) for part in sys.version_info[:2])
        assert running == floor, (
            f"{REQUIRE}=1, so this is the `{JOB}` job, and it is running Python {running} rather "
            f"than the pinned {floor}: the pin in {WORKFLOW} did not reach the interpreter"
        )
