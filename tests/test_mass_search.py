"""search_mass() and get_by_site() (1.1)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from uniprotptmpy import PtmDatabase, UniprotPtmError
from uniprotptmpy._mass import POSITIONS, parse_position, parse_site, slot_matches
from uniprotptmpy.database import _slots


def _mass(entry) -> float | None:
    return entry.get_mass()


def _brute(db: PtmDatabase, delta, tolerance=0.01, unit="da", site=None, position=None):
    """Linear scan reference: every entry, inclusive window test, sorted by (|error|, mass, order)."""
    assert unit == "da"
    tol = tolerance + 1e-9 * max(1.0, abs(delta))  # inclusive edges, same slack as the index
    sq = parse_site(site, UniprotPtmError) if site is not None else None
    pq = parse_position(position, UniprotPtmError) if position is not None else None
    hits = []
    for i, e in enumerate(db):
        m = _mass(e)
        if m is None or not math.isfinite(m) or abs(delta - m) > tol:
            continue
        if slot_matches(_slots(e), sq, pq):
            hits.append((abs(delta - m), m, i, e, delta - m))
    hits.sort(key=lambda h: h[:3])
    return [(h[3], h[4]) for h in hits]


def _names(hits) -> list[str]:
    return [e.name for e, _ in hits]


# ---------------------------------------------------------------- hand-checked


def test_phospho_on_sty(db: PtmDatabase) -> None:
    hits = db.search_mass(79.966, site="STY")
    assert _names(hits)[: len(["Phosphoserine", "Phosphothreonine", "Phosphotyrosine"])] == [
        "Phosphoserine",
        "Phosphothreonine",
        "Phosphotyrosine",
    ]
    entry, error = hits[0]
    assert error == pytest.approx(79.966 - 79.966331, abs=1e-5)
    assert all(abs(err) <= 0.01 for _, err in hits)
    assert [abs(err) for _, err in hits] == sorted(abs(err) for _, err in hits)


def test_oxidation_on_m(db: PtmDatabase) -> None:
    hits = db.search_mass(15.995, site="m")
    assert "Methionine sulfoxide" in _names(hits)
    assert all(abs(err) <= 0.01 for _, err in hits)


def test_tighter_window_drops_sulfo(db: PtmDatabase) -> None:
    # Sulfo (79.956815) is 9.5 mDa from phospho: inside 0.01 Da, outside 0.005 Da.
    wide = _names(db.search_mass(79.966331, tolerance=0.01))
    tight = _names(db.search_mass(79.966331, tolerance=0.005))
    assert "Sulfoserine" in wide
    assert "Sulfoserine" not in tight
    assert "Phosphoserine" in tight
    assert set(tight) < set(wide)


def test_window_edges_are_inclusive(db: PtmDatabase) -> None:
    # 79.976331 - 79.966331 is 0.010000000000005 in floats: still inside tolerance=0.01.
    assert "Phosphoserine" in _names(db.search_mass(79.976331, tolerance=0.01))
    assert "Phosphoserine" in _names(db.search_mass(79.956331, tolerance=0.01))
    assert "Phosphoserine" not in _names(db.search_mass(79.976332, tolerance=0.01))


def test_n_terminal_acetyl_position(db: PtmDatabase) -> None:
    assert "N-acetylalanine" in _names(db.search_mass(42.010565, site="A", position="protein n-term"))
    assert "N-acetylalanine" in _names(db.search_mass(42.010565, site="A", position="Protein N-term"))
    assert "N-acetylalanine" not in _names(db.search_mass(42.010565, site="A", position="anywhere"))


def test_uniprot_crosslink_residues_and_positions(db: PtmDatabase) -> None:
    from uniprotptmpy.database import _slots

    crosslinks = [e for e in db if "-" in e.target and e.target != "Undefined"]
    assert crosslinks
    for e in crosslinks:
        assert len(_slots(e)) == len(e.target.split("-"))
    asx = next(e for e in db if e.target == "Asparagine or Aspartate")
    assert asx in db.get_by_site("N") and asx in db.get_by_site("D")


def test_uniprot_lysine_acetyl_anywhere(db: PtmDatabase) -> None:
    assert "N6-acetyllysine" in _names(db.search_mass(42.010565, site="K", position="anywhere"))


def test_negative_delta(db: PtmDatabase) -> None:
    hits = db.search_mass(-17.026549, tolerance=0.001)
    assert hits
    assert all(_mass(e) < 0 for e, _ in hits)
    assert "Pyrrolidone carboxylic acid" in _names(hits)


def test_zero_tolerance_is_exact(db: PtmDatabase) -> None:
    target = next(e for e in db if _mass(e) is not None and _mass(e) > 1)
    hits = db.search_mass(_mass(target), tolerance=0)
    assert target in [e for e, _ in hits]
    assert all(abs(err) <= 1e-9 * max(1.0, abs(_mass(target))) for _, err in hits)
    assert db.search_mass(_mass(target) + 1e-6, tolerance=0) == []


def test_no_filters_returns_every_entry_in_window(db: PtmDatabase) -> None:
    assert db.search_mass(1e7) == []
    everything = db.search_mass(0, tolerance=1e7)
    assert len(everything) == sum(_mass(e) is not None for e in db)


def test_entries_without_mass_are_skipped(db: PtmDatabase) -> None:
    assert any(_mass(e) is None for e in db)
    assert all(_mass(e) is not None for e, _ in db.search_mass(0, tolerance=1e7))


def test_site_n_term_query_is_valid(db: PtmDatabase) -> None:
    hits = db.search_mass(42.010565, site="N-term")
    assert _names(hits) == _names(_brute(db, 42.010565, site="N-term"))


def test_result_is_fresh_list(db: PtmDatabase) -> None:
    db.search_mass(79.966).clear()
    assert db.search_mass(79.966)


# ---------------------------------------------------------------- errors


@pytest.mark.parametrize("site", ["B", "J", "Z", "1", "", "  ", "S-T", "N_term", 5])
def test_unknown_site_raises(db: PtmDatabase, site: object) -> None:
    with pytest.raises(UniprotPtmError, match="site"):
        db.search_mass(79.966, site=site)  # type: ignore[arg-type]


@pytest.mark.parametrize("position", ["middle", "n-term", "", 3])
def test_unknown_position_raises(db: PtmDatabase, position: object) -> None:
    with pytest.raises(UniprotPtmError, match="position"):
        db.search_mass(79.966, position=position)  # type: ignore[arg-type]


@pytest.mark.parametrize("unit", ["ppm", "PPM", "Da", "DA", " da", "da ", "mda", "", None, 1])
def test_unknown_unit_raises(db: PtmDatabase, unit: object) -> None:
    with pytest.raises(UniprotPtmError, match="unit"):
        db.search_mass(79.966, unit=unit)  # type: ignore[arg-type]


@pytest.mark.parametrize("delta", [math.nan, math.inf, -math.inf, "79.9", None, True])
def test_bad_delta_raises(db: PtmDatabase, delta: object) -> None:
    with pytest.raises(UniprotPtmError, match="delta"):
        db.search_mass(delta)  # type: ignore[arg-type]


@pytest.mark.parametrize("tolerance", [-0.01, math.nan, math.inf, "0.01", None, False])
def test_bad_tolerance_raises(db: PtmDatabase, tolerance: object) -> None:
    with pytest.raises(UniprotPtmError, match="tolerance"):
        db.search_mass(79.966, tolerance=tolerance)  # type: ignore[arg-type]


def test_errors_are_the_package_error(db: PtmDatabase) -> None:
    with pytest.raises(UniprotPtmError) as info:
        db.search_mass(79.966, site="B")
    assert type(info.value) is UniprotPtmError


# ---------------------------------------------------------------- property: index == brute force

_sites = st.one_of(st.none(), st.sampled_from(["S", "STY", "K", "M", "C", "N", "Q", "X", "N-term", "C-term", "ndq"]))
_positions = st.one_of(st.none(), st.sampled_from([*POSITIONS, "Any N-term", "any c-term"]))


@given(
    delta=st.floats(min_value=-200, max_value=1500, allow_nan=False),
    tolerance=st.floats(min_value=0, max_value=5, allow_nan=False),
    site=_sites,
    position=_positions,
)
def test_matches_brute_force_da(db: PtmDatabase, delta, tolerance, site, position) -> None:
    assert db.search_mass(delta, tolerance=tolerance, site=site, position=position) == _brute(
        db, delta, tolerance, "da", site, position
    )


@given(
    entry_index=st.integers(min_value=0, max_value=10_000),
    offset=st.floats(min_value=-0.05, max_value=0.05, allow_nan=False),
    tolerance=st.floats(min_value=0, max_value=0.05, allow_nan=False),
    site=_sites,
    position=_positions,
)
def test_matches_brute_force_near_real_masses(db: PtmDatabase, entry_index, offset, tolerance, site, position) -> None:
    masses = [_mass(e) for e in db if _mass(e) is not None]
    delta = masses[entry_index % len(masses)] + offset
    got = db.search_mass(delta, tolerance=tolerance, site=site, position=position)
    assert got == _brute(db, delta, tolerance, "da", site, position)


# ---------------------------------------------------------------- get_by_site


def test_get_by_site(db: PtmDatabase) -> None:
    s = db.get_by_site("S")
    assert s
    assert s == db.get_by_site(" s ")
    order = {id(e): i for i, e in enumerate(db)}
    assert [order[id(e)] for e in s] == sorted(order[id(e)] for e in s)
    assert ["Phosphoserine", "Phosphothreonine", "Phosphotyrosine"][0] in [e.name for e in s]
    assert len(set(map(id, s))) == len(s)


@pytest.mark.parametrize("site", ["B", "", "zz", None, 5])
def test_get_by_site_unknown_is_empty(db: PtmDatabase, site: object) -> None:
    assert db.get_by_site(site) == []  # type: ignore[arg-type]


def test_get_by_site_returns_fresh_list(db: PtmDatabase) -> None:
    db.get_by_site("S").clear()
    assert db.get_by_site("S")
