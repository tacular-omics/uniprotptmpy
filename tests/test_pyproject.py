"""Packaging metadata: the sibling pin policy for the ``link`` extra and the dev group.

Deliberately imports nothing optional, so it runs in a plain install and in the
isolated job, which is where a miswritten pin would reach a user.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

CLAUSE = re.compile(r"^(?P<op><=|>=|==|!=|~=|<|>)\s*(?P<version>[0-9][0-9a-zA-Z.*+!-]*)$")


def _pins(requirements: list[str]) -> dict[str, dict[str, tuple[int, ...]]]:
    """Each requirement as its name and its specifier clauses, parsed not matched as text."""
    pins: dict[str, dict[str, tuple[int, ...]]] = {}
    for requirement in requirements:
        split = re.match(r"^(?P<name>[A-Za-z0-9._-]+)(?P<specifiers>.*)$", requirement.strip())
        assert split is not None, f"cannot parse requirement {requirement!r}"
        specifiers = {}
        for part in split["specifiers"].split(","):
            matched = CLAUSE.match(part.strip())
            assert matched is not None, f"{requirement!r}: cannot parse specifier {part!r}"
            specifiers[matched["op"]] = tuple(int(n) for n in re.findall(r"\d+", matched["version"]))
        pins[split["name"]] = specifiers
    return pins


def test_link_extra_pins_both_siblings_with_a_cap() -> None:
    """The ``link`` extra names exactly the two siblings, each with a floor and a major cap."""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    pins = _pins(pyproject["project"]["optional-dependencies"]["link"])

    # The tacular-omics sibling pin policy: a >= floor and a < cap on the next major, or on the
    # next minor for a 0.x sibling. Bumping a sibling to 2.x keeps the test honest instead of
    # breaking it, and an uncapped or reordered pin does not pass.
    assert set(pins) == {"psimodpy", "unimodpy"}
    for name, specifiers in pins.items():
        assert set(specifiers) == {">=", "<"}, f"{name} needs a >= floor and a < cap, got {sorted(specifiers)}"
        floor, cap = specifiers[">="], specifiers["<"]
        assert floor < cap, f"{name}: floor {floor} is not below cap {cap}"
        if floor[0]:
            expected = (floor[0] + 1,)
        else:
            expected = (0, (floor[1] if len(floor) > 1 else 0) + 1)
        assert cap[: len(expected)] == expected, f"{name}: cap {cap} does not cap at {expected}"


def test_dev_group_declares_tacular_for_the_agreement_tests() -> None:
    """``tests/test_data_agreement.py`` skips without tacular, so the declaration is load-bearing.

    Without this, removing tacular from the dev group would turn the agreement tests into a
    permanent silent skip rather than a failure, which is how a data drift would reach a release.
    """
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    requirements = [
        requirement
        for requirement in pyproject["dependency-groups"]["dev"]
        if re.match(r"^tacular\b", requirement.strip())
    ]
    assert len(requirements) == 1, f"the dev group must declare tacular exactly once, got {requirements}"

    specifiers = _pins(requirements)["tacular"]
    assert set(specifiers) == {">=", "<"}, f"tacular needs a >= floor and a < cap, got {sorted(specifiers)}"
    assert specifiers[">="] < specifiers["<"]

    # tacular must not be a runtime or extra dependency: the agreement tests are the only use.
    assert "tacular" not in " ".join(pyproject["project"].get("dependencies", []))
    for extra, pins in pyproject["project"].get("optional-dependencies", {}).items():
        assert not any(re.match(r"^tacular\b", pin.strip()) for pin in pins), (
            f"tacular must stay dev-only, found it in the {extra} extra"
        )
