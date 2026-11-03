"""Packaging metadata: the sibling pin policy for the ``link`` extra.

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
