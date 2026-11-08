"""Which optional extras the running environment has, asserted as an equality.

``pip install uniprotptmpy`` is what most users get, and the core package declares no
runtime dependencies at all. Every other CI job installs ``--all-extras``, so without
the ``no-extras`` job nothing any developer or any job runs would ever enter the user's
environment. A skip count or a collected total cannot stand in for this: where
``pytest.importorskip`` sits decides which of the two moves, so each goes blind in one
scope or the other. ``UNIPROTPTMPY_EXPECT_EXTRAS`` names the extras the job installed,
and the comparison is an exact set equality per extra, per distribution.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import tomllib
from pathlib import Path

import pytest

EXPECT_EXTRAS = "UNIPROTPTMPY_EXPECT_EXTRAS"
ROOT = Path(__file__).parents[1]
# The jobs in ci.yml that run the suite. An equality, so adding or removing one fails
# here rather than quietly leaving a job unchecked.
SUITE_JOBS = {"test", "lowest", "coverage", "no-extras"}


def extra_requirements() -> dict[str, set[str]]:
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


def is_installed(distribution: str) -> bool:
    """Whether `distribution` is installed, by its metadata rather than by importing it."""
    try:
        importlib.metadata.distribution(distribution)
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def declared_extras() -> set[str]:
    """The extras the job says it installed; skips when nothing says."""
    value = os.environ.get(EXPECT_EXTRAS)
    if value is None:
        pytest.skip(f"{EXPECT_EXTRAS} is unset, so there is nothing to hold the environment to")
    if value.strip() == "none":
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def ci_jobs() -> dict[str, str]:
    """ci.yml split into job bodies, comments removed: a two-space key below `jobs:` starts one.

    The comments have to go, or a job that mentions a flag in prose reads as a job that
    passes it, which is how the check below first failed.
    """
    lines = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").splitlines()
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[lines.index("jobs:") + 1 :]:
        matched = re.match(r"^ {2}(?P<name>[A-Za-z0-9_-]+):\s*$", line)
        if matched:
            current = matched["name"]
            bodies[current] = []
        elif current is not None:
            bodies[current].append(re.sub(r"\s+#.*$", "", line) if not line.lstrip().startswith("#") else "")
    assert bodies, "no jobs parsed out of ci.yml"
    return {name: "\n".join(body) for name, body in bodies.items()}


def test_the_installed_extras_are_exactly_the_declared_ones() -> None:
    extras = extra_requirements()
    wanted = declared_extras()
    unknown = wanted - set(extras)
    assert not unknown, f"{EXPECT_EXTRAS} names an extra the pyproject does not declare: {sorted(unknown)}"
    for extra, distributions in sorted(extras.items()):
        present = {name for name in distributions if is_installed(name)}
        expected = distributions if extra in wanted else set()
        assert present == expected, f"extra {extra!r}: installed {sorted(present)}, expected {sorted(expected)}"


def test_every_job_that_runs_the_suite_declares_the_extras_it_installed() -> None:
    jobs = ci_jobs()
    running = {name: body for name, body in jobs.items() if "pytest tests" in body}
    assert set(running) == SUITE_JOBS, f"ci.yml runs the suite in {sorted(running)}"
    for name, body in sorted(running.items()):
        found = re.search(rf"{EXPECT_EXTRAS}: *(?P<value>\S+)", body)
        assert found is not None, f"job {name!r} runs the suite without declaring {EXPECT_EXTRAS}"
        # The declaration has to agree with the install line, or it is just a label.
        installs_extras = "--all-extras" in body
        assert (found["value"] != "none") == installs_extras, (
            f"job {name!r} declares {EXPECT_EXTRAS}: {found['value']} but installs "
            f"{'with' if installs_extras else 'without'} --all-extras"
        )
