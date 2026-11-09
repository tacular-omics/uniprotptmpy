"""Execute every docstring example in the package.

A ``>>>`` example is the only documentation the suite can keep honest, so the walk below
imports every module and runs whatever examples it finds. The package has none today
(measured 2026-11-09), which is why this is scaffolding: ``MIN_EXAMPLES`` is 0 and that
assertion is inert until the first example lands, while the module floors do the work of
catching a walk that silently collects nothing.

The fenced blocks in ``README.md`` are a different surface and nothing here runs them.
"""

from __future__ import annotations

import doctest
import importlib
import importlib.util
import pkgutil
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import uniprotptmpy

ROOT = Path(__file__).parents[1]

# Measured 2026-11-09. Raise these when you add modules or examples; never lower one
# without saying why in the commit message. Both floors hold in EVERY environment: the
# server count includes the modules excluded by name, so a module that vanished from
# server/ fails the test in the no-extras job too, where none of them can be imported.
MIN_CORE_MODULES = 11
MIN_SERVER_MODULES = 4
MIN_EXAMPLES = 0

# Nothing under `uniprotptmpy.server` can be imported without the `server` extra:
# server/__init__.py imports server.app, which imports fastapi, mcp and pydantic at module
# scope. So the subtree is excluded BY NAME, and only where that extra is absent -- which
# is what CI's `no-extras` job installs. The test asks whether the EXTRA is installed, not
# whether one chosen name is: an extra arrives as a whole dependency set, and keying the
# question to a single name is how a partial environment (fastapi present, mcp absent)
# produced a red test. `test_server_requires_is_exactly_the_declared_extra` keeps this
# tuple equal to the pyproject, so adding a dependency to the extra cannot leave it short.
SERVER = "uniprotptmpy.server"
SERVER_REQUIRES = ("fastapi", "mcp", "pydantic", "uvicorn")


def installed(distribution: str) -> bool:
    """Whether `distribution` can be located, without importing it."""
    try:
        return importlib.util.find_spec(distribution) is not None
    except ModuleNotFoundError:
        return False


def server_extra_installed() -> bool:
    """Whether the whole `server` extra is present, which is what its subtree needs."""
    return all(installed(distribution) for distribution in SERVER_REQUIRES)


def unavailable(name: str) -> bool:
    """Whether `name` is in the server subtree in an environment that lacks its extra."""
    return (name == SERVER or name.startswith(f"{SERVER}.")) and not server_extra_installed()


def server_subtree_names() -> list[str]:
    """Every name under `server/`, read off the filesystem rather than by importing it.

    `pkgutil` never yields the children of a package it could not import, so without this
    the excluded modules would be invisible and the server floor could only be asserted
    where the extra happens to be installed. That conditional floor is the defect this
    replaces: it was keyed to one name, so a partial environment made it fire with nothing
    to count.
    """
    directory = Path(uniprotptmpy.__path__[0]) / "server"
    names = [SERVER]
    names.extend(name for _finder, name, _ispkg in pkgutil.iter_modules([str(directory)], prefix=f"{SERVER}."))
    return names


def on_import_error(name: str) -> None:
    """Never swallow: `walk_packages` drops a package it cannot import when `onerror` is None.

    Which branch of this runs was measured on 2026-11-09, because a guard whose firing
    nobody has watched is a guard nobody has tested. `pkgutil.walk_packages` yields a
    package BEFORE importing it to recurse, so `import_module` below reaches a broken
    module first and this is never asked about it: in a full environment with
    server/__init__.py broken, `on_import_error` was called 0 times and the walk raised
    from `import_module`. The branch that does run is the early return, once, for a
    subtree excluded by name in an environment without its extra. The raise is therefore
    defence against a shape this package does not have today (a package `import_module`
    can import and `__import__` cannot), kept because the alternative is the silent drop.
    """
    if unavailable(name):
        return
    raise ImportError(f"walk_packages could not import {name}") from sys.exc_info()[1]


def import_module(name: str, ispkg: bool) -> ModuleType:
    """Import `name`, failing the test with the dotted name rather than a bare ImportError."""
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        reached = ", so nothing under it was walked" if ispkg else ""
        raise AssertionError(f"walking into {name} failed{reached}: {exc!r}") from exc


def all_modules() -> list[ModuleType]:
    """Every importable module in the package, the package itself included, in walk order."""
    modules = [uniprotptmpy]
    for _finder, name, ispkg in pkgutil.walk_packages(
        uniprotptmpy.__path__, prefix=f"{uniprotptmpy.__name__}.", onerror=on_import_error
    ):
        if unavailable(name):
            continue
        modules.append(import_module(name, ispkg))
    return modules


def declared_server_extra() -> set[str]:
    """The distribution names the pyproject's `server` extra requires."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = pyproject["project"]["optional-dependencies"]["server"]
    names = set()
    for requirement in requirements:
        matched = re.match(r"^(?P<name>[A-Za-z0-9._-]+)", requirement.strip())
        assert matched is not None, f"cannot parse requirement {requirement!r}"
        names.add(matched["name"])
    assert names, "the `server` extra declares nothing"
    return names


def test_server_requires_is_exactly_the_declared_extra() -> None:
    """The gate above must name the whole extra, which only the pyproject knows."""
    assert set(SERVER_REQUIRES) == declared_server_extra(), (
        f"SERVER_REQUIRES is {sorted(SERVER_REQUIRES)} but the `server` extra declares "
        f"{sorted(declared_server_extra())}; an import name that differs from the "
        f"distribution name has to be handled here on purpose, not by being left out"
    )


def test_docstring_examples() -> None:
    modules = all_modules()
    names = [module.__name__ for module in modules]
    imported_server = [name for name in names if name == SERVER or name.startswith(f"{SERVER}.")]
    excluded_server = [] if server_extra_installed() else server_subtree_names()
    core = [name for name in names if name not in imported_server]
    server = imported_server + excluded_server
    assert len(core) >= MIN_CORE_MODULES, f"the module walk found only {len(core)} core modules: {core}"
    assert len(server) >= MIN_SERVER_MODULES, f"only {len(server)} server modules were imported or excluded: {server}"
    attempted = failed = 0
    for module in modules:
        result = doctest.testmod(module, verbose=False)
        attempted += result.attempted
        failed += result.failed
    assert failed == 0, f"{failed} of {attempted} docstring examples failed"
    assert attempted >= MIN_EXAMPLES, f"only {attempted} examples ran, expected >= {MIN_EXAMPLES}"
