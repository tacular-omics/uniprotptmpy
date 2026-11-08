"""An optional dependency must stay out of ``sys.modules`` until something asks for it.

The core package declares no runtime dependencies, and ``entry.resolve`` imports
``psimodpy``/``unimodpy`` lazily. Both properties are invisible to
``importlib.util.find_spec`` in an environment where the extras are installed, which is
every environment this suite normally runs in, so each check below runs in a
``python -I`` subprocess and reads ``sys.modules`` after the import under test.
"""

from __future__ import annotations

import importlib.util
import pkgutil
import subprocess
import sys

import pytest

import uniprotptmpy

# The `server` extra plus the web stack it pulls in transitively.
SERVER_PACKAGES = ("fastapi", "mcp", "pydantic", "starlette", "uvicorn")
# The `link` extra.
LINK_PACKAGES = ("psimodpy", "unimodpy")

# Every module `import uniprotptmpy` loads. The subprocesses below assert over
# `sys.modules`, so they only cover what the package import actually loads; the modules
# are named here so that test_every_core_module_is_covered fails when one is added.
CORE_MODULES = (
    "uniprotptmpy._download",
    "uniprotptmpy._formula",
    "uniprotptmpy._links",
    "uniprotptmpy._mass",
    "uniprotptmpy._ptmlist_writer",
    "uniprotptmpy._tabular",
    "uniprotptmpy.database",
    "uniprotptmpy.errors",
    "uniprotptmpy.models",
    "uniprotptmpy.parser",
)


def installed(names: tuple[str, ...]) -> list[str]:
    """The subset of `names` that this environment can import."""
    return [name for name in names if importlib.util.find_spec(name) is not None]


def run_isolated(code: str) -> None:
    """Run `code` in a fresh interpreter, failing with its stderr."""
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr


def boundary_code(import_line: str, forbidden: list[str], expect_loaded: tuple[str, ...]) -> str:
    """Code asserting `import_line` loads `expect_loaded` and none of `forbidden`."""
    return "\n".join(
        (
            "import importlib.util",
            "import sys",
            import_line,
            f"forbidden = {list(forbidden)!r}",
            f"expected = {list(expect_loaded)!r}",
            "absent = [name for name in forbidden if importlib.util.find_spec(name) is None]",
            "assert not absent, 'not installed here, so the check is vacuous: ' + repr(absent)",
            "leaked = [name for name in forbidden if name in sys.modules]",
            "assert not leaked, 'imported without being asked for: ' + repr(leaked)",
            "missing = [name for name in expected if name not in sys.modules]",
            "assert not missing, 'the import under test did not load: ' + repr(missing)",
        )
    )


def test_every_core_module_is_covered() -> None:
    found = {module.name for module in pkgutil.iter_modules(uniprotptmpy.__path__, "uniprotptmpy.")}
    assert found - {"uniprotptmpy.server"} == set(CORE_MODULES)


def test_importing_the_package_pulls_in_no_optional_dependency() -> None:
    forbidden = installed(SERVER_PACKAGES + LINK_PACKAGES)
    if not forbidden:
        pytest.skip("no optional dependency is installed, so nothing can leak")
    run_isolated(boundary_code("import uniprotptmpy", forbidden, CORE_MODULES))


def test_core_operations_pull_in_no_link_dependency() -> None:
    forbidden = installed(LINK_PACKAGES)
    if not forbidden:
        pytest.skip("neither psimodpy nor unimodpy is installed, so nothing can leak")
    work = "\n".join(
        (
            "import tempfile",
            "from pathlib import Path",
            "db = uniprotptmpy.load()",
            "assert len(db) == 750",
            "entry = db['PTM-0253']",
            "assert entry.psimod_ids == ('MOD:00046',) and entry.unimod_ids == ('UNIMOD:21',)",
            "assert entry.proforma_formula == 'HO3P'",
            "assert len(db.search('phospho')) == 41",
            "assert len(db.search_mass(79.96633, tolerance=0.01)) == 13",
            "with tempfile.TemporaryDirectory() as directory:",
            "    path = Path(directory) / 'out.tsv'",
            "    db.write_tsv(path)",
            "    assert path.read_text(encoding='utf-8')",
        )
    )
    run_isolated(boundary_code("import uniprotptmpy\n" + work, forbidden, CORE_MODULES))


def test_importing_the_server_pulls_in_no_link_dependency() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("mcp")
    forbidden = installed(LINK_PACKAGES)
    if not forbidden:
        pytest.skip("neither psimodpy nor unimodpy is installed, so nothing can leak")
    expected = (*CORE_MODULES, "uniprotptmpy.server", "uniprotptmpy.server.app", "uniprotptmpy.server.models")
    run_isolated(boundary_code("import uniprotptmpy.server", forbidden, expected))


def test_importing_the_server_does_pull_in_the_server_extra() -> None:
    """The server boundary is one-way: `server` may import its own extra, and does."""
    forbidden = installed(SERVER_PACKAGES)
    if sorted(forbidden) != sorted(SERVER_PACKAGES):
        pytest.skip("the server extra is not installed")
    run_isolated(
        "\n".join(
            (
                "import sys",
                "import uniprotptmpy.server",
                f"expected = {list(SERVER_PACKAGES)!r}",
                "missing = [name for name in expected if name not in sys.modules]",
                "assert not missing, 'server stopped importing: ' + repr(missing)",
            )
        )
    )
