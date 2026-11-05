"""Adding ``position`` to a ``search_mass`` query must narrow the result set, never widen it.

Stated as a subset invariant over a sweep of queries, because the failure mode is silent:
a filter that adds hits gives a wrong answer the caller has no reason to doubt.

For the UniProt vocabulary the fix behind this file changes nothing: no entry here has a
terminus specificity, so the clause it corrects never fires (see
``test_no_slot_in_the_vocabulary_is_a_terminus_slot``). These tests are the guard that keeps
it that way, plus one unit test of the clause itself, which the bundled data cannot reach.
"""

from __future__ import annotations

import pytest

from uniprotptmpy import PtmDatabase
from uniprotptmpy._mass import C_TERM, N_TERM, POSITIONS, WHERE_ANY_C, WHERE_ANY_N, parse_site, slot_matches
from uniprotptmpy.database import _slots
from uniprotptmpy.errors import UniprotPtmError

# The nine most common delta masses in the bundled release, so each query has hits to lose.
_DELTAS = (-18.010565, 14.015650, 15.994915, -2.015650, 162.052823, -0.984016, 203.079373, 42.010565, -17.026549)
_SITES = (None, "C", "S", "K", "N", "T", "Y", "G", "R", "P", "D", "H", "N-term", "C-term", "ST", "STY")


def _ids(hits) -> set[str]:
    return {entry.accession for entry, _ in hits}


@pytest.mark.parametrize("position", POSITIONS)
def test_position_only_removes_hits(db: PtmDatabase, position: str) -> None:
    widened = []
    for delta in _DELTAS:
        for site in _SITES:
            without = _ids(db.search_mass(delta, tolerance=0.02, site=site))
            with_position = _ids(db.search_mass(delta, tolerance=0.02, site=site, position=position))
            extra = with_position - without
            if extra:
                widened.append((delta, site, sorted(extra)[:5]))
    assert not widened, f"position={position!r} added hits for {len(widened)} queries: {widened[:5]}"


def test_the_sweep_actually_removes_hits(db: PtmDatabase) -> None:
    """The subset invariant is only worth asserting if some query is narrowed at all."""
    narrowed = 0
    for delta in _DELTAS:
        for site in _SITES:
            without = _ids(db.search_mass(delta, tolerance=0.02, site=site))
            for position in POSITIONS:
                if _ids(db.search_mass(delta, tolerance=0.02, site=site, position=position)) < without:
                    narrowed += 1
    assert narrowed > 0


def test_no_slot_in_the_vocabulary_is_a_terminus_slot(db: PtmDatabase) -> None:
    """Why the fix is a no-op here: ``sites`` is always residue letters, never a terminus name.

    ptmlist.txt states the modified residue in ``TG`` and the polypeptide position in ``PP``, so a
    terminus only ever reaches ``where``, never ``sites``. unimodpy's data does both, which is where
    the bug was visible. If a future release adds a terminus specificity this test fails first and
    says so, rather than the invariant above silently starting to carry weight.
    """
    offenders = [(e.accession, sites) for e in db for sites, _ in _slots(e) if sites & {N_TERM, C_TERM}]
    assert offenders == []


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (None, True),  # was False before the fix: the least-constrained query was the narrowest one
        ("peptide n-term", True),
        ("protein n-term", True),
        ("anywhere", False),  # a residue inside the sequence is at neither terminus
        ("peptide c-term", False),
    ],
)
def test_a_terminus_slot_matches_a_residue_query_while_that_terminus_is_open(
    position: str | None, expected: bool
) -> None:
    """``slot_matches`` on a synthetic N-terminus slot: the bundled data has none to test with.

    ``position=None`` constrains nothing, so it must match everything a stated position matches.
    Before the fix it matched *less*, which is the widening the sweep above guards against.
    """
    slots = ((frozenset({N_TERM}), WHERE_ANY_N),)
    site = parse_site("A", UniprotPtmError)
    assert slot_matches(slots, site, position) is expected


def test_a_terminus_site_query_still_matches_its_own_terminus_slot() -> None:
    """The fix must not disturb the ``site="N-term"`` path, which matches on ``sites`` directly."""
    slots = ((frozenset({C_TERM}), WHERE_ANY_C),)
    site = parse_site("C-term", UniprotPtmError)
    assert slot_matches(slots, site, None) is True
    assert slot_matches(slots, site, "peptide c-term") is True
    assert slot_matches(slots, site, "anywhere") is False
