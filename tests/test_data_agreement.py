"""Cross-check the bundled UniProt-PTM vocabulary against tacular's bundled copy.

tacular ships its own table built from the same UniProt release (``tacular._datagen``),
so every accession both packages carry must agree on mass and composition. A failure
lists every disagreeing entry; fix the cause - a parser bug on either side, or one copy
updated to a newer release than the other - do not loosen the comparison.

The scope difference is asserted rather than tolerated: tacular ships exactly the entries
that have a correction formula and are not crosslinks, because a crosslink's values are
compound. Keeping that an equality means a future entry dropped from either side fails
here instead of passing as "out of scope".

Skipped when tacular is not installed (it is a dev-only dependency, never a runtime one).
``tests/test_pyproject.py`` asserts the dev group still declares it, so this module cannot
become a permanent silent skip by someone removing the dependency.
"""

from __future__ import annotations

import math
import re
from importlib.resources import files

import pytest

import uniprotptmpy
from uniprotptmpy import FeatureType, PtmEntry

MASS_ABS_TOL = 1e-6

#: The feature type tacular omits: its values describe a link between two residues.
COMPOUND_FEATURE_TYPE = FeatureType.CROSSLNK

_RELEASE = re.compile(r"^Release:\s+(?P<release>.+?)\s*$", re.MULTILINE)


@pytest.fixture(scope="module")
def lookup():
    tacular = pytest.importorskip(
        "tacular",
        reason="tacular is a dev-only dependency of uniprotptmpy; install the dev group to run the agreement tests",
    )
    return tacular.UNIPROT_PTM_LOOKUP


@pytest.fixture(scope="module")
def entries() -> dict[str, PtmEntry]:
    """Our entries by bare accession number, which is how tacular keys its table."""
    return {entry.accession.removeprefix("PTM-"): entry for entry in uniprotptmpy.load()}


def _bundled_release() -> str:
    """The ``Release:`` line of the bundled ptmlist.txt, which the parser does not keep."""
    text = (files("uniprotptmpy") / "data" / "ptmlist.txt").read_text(encoding="utf-8")
    matched = _RELEASE.search(text)
    assert matched is not None, "the bundled ptmlist.txt has no Release: line"
    return matched["release"]


def _in_tacular_scope(entry: PtmEntry) -> bool:
    return entry.dict_composition is not None and entry.feature_type is not COMPOUND_FEATURE_TYPE


def test_same_data_release(lookup) -> None:
    """Both copies are built from the same UniProt release, so neither can drift unnoticed."""
    assert lookup.version == _bundled_release()


def test_masses_and_compositions_agree(lookup, entries) -> None:
    """Every accession both packages ship agrees on monoisotopic mass, average mass and composition."""
    problems: list[str] = []
    for info in lookup.values():
        entry = entries.get(info.id)
        if entry is None:
            problems.append(f"PTM-{info.id} {info.name!r}: missing from uniprotptmpy")
            continue
        for attribute, theirs, ours in (
            ("monoisotopic mass", info.monoisotopic_mass, entry.monoisotopic_mass),
            ("average mass", info.average_mass, entry.average_mass),
        ):
            if (theirs is None) != (ours is None) or (
                theirs is not None and not math.isclose(theirs, ours, rel_tol=0, abs_tol=MASS_ABS_TOL)
            ):
                problems.append(f"PTM-{info.id} {info.name!r}: {attribute} tacular={theirs} uniprotptmpy={ours}")
        theirs_composition = dict(info.dict_composition or {})
        ours_composition = dict(entry.dict_composition or {})
        if theirs_composition != ours_composition:
            problems.append(
                f"PTM-{info.id} {info.name!r}: composition tacular={theirs_composition} uniprotptmpy={ours_composition}"
            )
    assert not problems, f"{len(problems)} disagreements with tacular:\n" + "\n".join(problems)


def test_tacular_ships_nothing_we_lack(lookup, entries) -> None:
    """tacular is a subset: an accession only it carries means our parser dropped an entry."""
    missing = sorted(info.id for info in lookup.values() if info.id not in entries)
    assert not missing, f"{len(missing)} accessions in tacular and not in uniprotptmpy: {missing}"


def test_our_extra_entries_are_exactly_what_tacular_excludes(lookup, entries) -> None:
    """The scope difference is an equality in both directions, not a tolerance."""
    theirs = {info.id for info in lookup.values()}
    expected = {accession for accession, entry in entries.items() if _in_tacular_scope(entry)}

    # PTM-0676 is why the rule is the correction formula and not the mass: it has a formula
    # and no MM, and tacular ships it.
    assert expected - theirs == set(), f"in tacular's scope but absent from it: {sorted(expected - theirs)}"
    assert theirs - expected == set(), f"in tacular and outside its scope: {sorted(theirs - expected)}"


def test_every_crosslink_is_ours_alone(lookup, entries) -> None:
    """tacular omits the compound feature type entirely, so every crosslink is uniprotptmpy-only."""
    theirs = {info.id for info in lookup.values()}
    crosslinks = {accession for accession, entry in entries.items() if entry.feature_type is COMPOUND_FEATURE_TYPE}
    assert crosslinks, "the bundled release has no crosslink entries, so this test proves nothing"
    assert crosslinks.isdisjoint(theirs)
