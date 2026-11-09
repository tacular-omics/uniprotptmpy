"""Execute every docstring example in the package.

A ``>>>`` example is the only documentation the suite can keep honest, so the walk below
imports every module and runs whatever examples it finds. The package has none today
(measured 2026-11-08), which is why this is scaffolding: ``MIN_EXAMPLES`` is 0 and that
assertion is inert until the first example lands, while the module floors do the work of
catching a walk that silently collects nothing.

The fenced blocks in ``README.md`` are a different surface and nothing here runs them.
"""

from __future__ import annotations

import doctest
import importlib
import importlib.util
import pkgutil
import sys
from types import ModuleType

import uniprotptmpy

# Measured 2026-11-08. Raise these when you add modules or examples; never lower them
# without saying why in the commit message.
MIN_MODULES = 11
MIN_EXAMPLES = 0
# The `server` subpackage and its three modules, counted separately because they are
# excluded where the extra is absent: a floor of 11 would not notice all four vanishing
# from an environment that does have the extra.
MIN_SERVER_MODULES = 4

# `uniprotptmpy.server` imports fastapi and mcp at module top (see CLAUDE.md), so it
# cannot be imported without the `server` extra, which is exactly what the `no-extras` CI
# job installs. It is excluded BY NAME here, and only when the extra is absent: with the
# extra installed it is imported and its examples run like any other module's. MIN_MODULES
# is the count without it, so the floor holds in the leanest environment.
OPTIONAL_MODULES = {"uniprotptmpy.server": ("fastapi", "mcp")}


def unavailable(name: str) -> bool:
    """Whether `name` is (or is inside) an optional module this environment cannot import."""
    for module, requirements in OPTIONAL_MODULES.items():
        if name == module or name.startswith(f"{module}."):
            return any(importlib.util.find_spec(requirement) is None for requirement in requirements)
    return False


def on_import_error(name: str) -> None:
    """Re-raise: a module that stops importing must fail the suite, not drop out of the walk."""
    if unavailable(name):
        return
    raise ImportError(f"walk_packages could not import {name}") from sys.exc_info()[1]


def all_modules() -> list[ModuleType]:
    """Every module in the package, the package itself included, in walk order."""
    modules = [uniprotptmpy]
    for _finder, name, _ispkg in pkgutil.walk_packages(
        uniprotptmpy.__path__, prefix=f"{uniprotptmpy.__name__}.", onerror=on_import_error
    ):
        if unavailable(name):
            continue
        modules.append(importlib.import_module(name))
    return modules


def test_docstring_examples() -> None:
    modules = all_modules()
    names = [module.__name__ for module in modules]
    assert len(modules) >= MIN_MODULES, f"module walk found only {len(modules)}: {names}"
    if importlib.util.find_spec("fastapi") is not None:
        server = [name for name in names if name.startswith("uniprotptmpy.server")]
        assert len(server) >= MIN_SERVER_MODULES, f"the server extra is installed but the walk found {server}"
    attempted = failed = 0
    for module in modules:
        result = doctest.testmod(module, verbose=False)
        attempted += result.attempted
        failed += result.failed
    assert failed == 0, f"{failed} of {attempted} docstring examples failed"
    assert attempted >= MIN_EXAMPLES, f"only {attempted} examples ran, expected >= {MIN_EXAMPLES}"
