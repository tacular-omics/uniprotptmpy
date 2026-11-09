"""Execute every docstring example in the package.

A ``>>>`` example is the only documentation the suite can keep honest, so the walk below
imports every module and runs whatever examples it finds. The package has none today
(measured 2026-11-09), which is why this is scaffolding: ``MIN_EXAMPLES`` is 0 and that
assertion is inert until the first example lands, while the module floors do the work of
catching a walk that silently collects nothing.

The fenced blocks in ``README.md`` are a different surface and nothing here runs them.
"""

from __future__ import annotations

import ast
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

# Nothing under `uniprotptmpy.server` can be imported without fastapi, mcp and pydantic:
# server/__init__.py imports server.app, which imports all three at module scope. So the
# subtree is excluded BY NAME, and only where one of those three cannot be located -- which
# is what CI's `no-extras` job installs.
#
# The predicate is EVERY ROOT THE MODULES IMPORT AT MODULE SCOPE. That is neither one name
# nor the declared extra, and the two wrong answers fail in opposite directions. One name is
# how a partial environment (fastapi present, mcp absent) produced a red test: the gate did
# not skip and the import blew up. The declared extra adds `uvicorn`, which the extra ships
# and nothing imports (measured 2026-11-08: one occurrence in src, a shell command inside
# server/__init__.py's docstring), so requiring it would skip a subtree that imports fine the
# moment uvicorn alone is missing, and a real defect under server/ would go unrun with
# nothing red. A tuple that is too short fails loudly on the import; a tuple that is too long
# skips in silence, which is the worse half, so this one is pinned to the source by
# `test_server_requires_is_every_module_scope_import_root`.
SERVER = "uniprotptmpy.server"
SERVER_REQUIRES = ("fastapi", "mcp", "pydantic")


def installed(distribution: str) -> bool:
    """Whether `distribution` can be located, without importing it."""
    try:
        return importlib.util.find_spec(distribution) is not None
    except ModuleNotFoundError:
        return False


def server_imports_available() -> bool:
    """Whether every root the server subtree imports at module scope can be located."""
    return all(installed(distribution) for distribution in SERVER_REQUIRES)


def unavailable(name: str) -> bool:
    """Whether `name` is in the server subtree in an environment that cannot import it."""
    return (name == SERVER or name.startswith(f"{SERVER}.")) and not server_imports_available()


def server_subtree_names() -> list[str]:
    """Every name under `server/`, read off the filesystem rather than by importing it.

    `pkgutil` never yields the children of a package it could not import, so without this
    the excluded modules would be invisible and the server floor could only be asserted
    where the imports happen to be installed. That conditional floor is the defect this
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


def server_import_roots() -> set[str]:
    """Every third-party root the server modules import at module scope, read as source.

    Read with `ast` rather than by importing, so this answers the same in the no-extras job
    as everywhere else. Module scope means `tree.body` and not `ast.walk`: an import inside
    `if TYPE_CHECKING:` or a `try` never runs at import time and so cannot stop the walk.
    """
    directory = Path(uniprotptmpy.__path__[0]) / "server"
    paths = sorted(directory.glob("*.py"))
    assert paths, f"no server modules to read under {directory}"
    roots: set[str] = set()
    for path in paths:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return {root for root in roots if root != uniprotptmpy.__name__ and root not in sys.stdlib_module_names}


def test_server_requires_is_every_module_scope_import_root() -> None:
    """The gate must name exactly what stops the import, which only the source knows.

    Equality in both directions, because the two errors are different bugs. A root missing
    from the tuple makes the walk attempt an import that cannot succeed: loud. A root in the
    tuple that nothing imports makes the walk skip a subtree that would have imported fine,
    so a defect under `server/` goes unrun and nothing goes red: silent, and the reason
    `uvicorn` is not in the tuple even though the `server` extra declares it.

    A root whose import name differs from its distribution name has to be mapped here on
    purpose rather than by being left out of one side.
    """
    assert set(SERVER_REQUIRES) == server_import_roots(), (
        f"SERVER_REQUIRES is {sorted(SERVER_REQUIRES)} but the server modules import "
        f"{sorted(server_import_roots())} at module scope"
    )


def test_server_requires_is_declared_by_the_server_extra() -> None:
    """Every root the gate names must be installable, which only the pyproject knows.

    Subset, not equality: a root no extra declares is a packaging bug, while a declared name
    nothing imports is allowed and is exactly `uvicorn`.
    """
    assert set(SERVER_REQUIRES) <= declared_server_extra(), (
        f"SERVER_REQUIRES is {sorted(SERVER_REQUIRES)} but the `server` extra declares only "
        f"{sorted(declared_server_extra())}; a root the server modules import has to be "
        f"declared by the extra that is supposed to supply it"
    )


def test_docstring_examples() -> None:
    modules = all_modules()
    names = [module.__name__ for module in modules]
    imported_server = [name for name in names if name == SERVER or name.startswith(f"{SERVER}.")]
    excluded_server = [] if server_imports_available() else server_subtree_names()
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
