"""Recompute every entry's masses from its parsed correction formula and compare with UniProt.

The element masses come from an independent table frozen from pyteomics (NIST); see
tests/reference/generate_element_masses.py. A mismatch means either the CF parser lost
or misread a token, or ptmlist.txt disagrees with itself. The second kind are listed in
KNOWN_MISMATCHES with the reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uniprotptmpy import PtmDatabase

_TABLE = json.loads((Path(__file__).parent / "reference" / "element_masses.json").read_text())
_ELEMENTS: dict[str, dict[str, float]] = _TABLE["elements"]
_ELECTRON: float = _TABLE["electron_mass"]

MONO_TOL = 5e-5  # MM is given to 6 decimals; atomic mass tables differ by up to ~1e-5
AVG_TOL = 0.02  # MA is given to 2 decimals

KNOWN_MISMATCHES: dict[str, str] = {
    "PTM-0681": "MM 781.125835 does not match CF C36 H41 N13 O17 P2 S1 (781.1459): upstream data error",
    "PTM-0741": "MM 104.0261 is C7 H4 O1 (104.026215) truncated, not rounded, to 4 decimals: upstream",
}

# Permanently charged (quaternary ammonium / sulfonium) residues: UniProt's MM is the
# formula's mass minus one electron. The CF itself carries no charge.
CATIONS = {
    "PTM-0118",
    "PTM-0177",
    "PTM-0179",
    "PTM-0186",
    "PTM-0187",
    "PTM-0400",
    "PTM-0430",
    "PTM-0503",
    "PTM-0636",
    "PTM-0672",
}


def _mass(composition: dict[str, int], kind: str) -> float:
    return sum(_ELEMENTS[token][kind] * count for token, count in composition.items())


def _mono(ptm_id: str, composition: dict[str, int]) -> float:
    return _mass(composition, "mono") - (_ELECTRON if ptm_id in CATIONS else 0.0)


def test_masses_match_correction_formula(db: PtmDatabase) -> None:
    mismatches = []
    checked = 0
    for e in db:
        if e.correction_formula is None or e.id in KNOWN_MISMATCHES:
            continue
        comp = e.dict_composition or {}
        if e.monoisotopic_mass is not None:
            checked += 1
            if abs(_mono(e.id, comp) - e.monoisotopic_mass) > MONO_TOL:
                mismatches.append((e.id, "MM", e.correction_formula, e.monoisotopic_mass, round(_mono(e.id, comp), 6)))
        if e.average_mass is not None and abs(_mass(comp, "avg") - e.average_mass) > AVG_TOL:
            mismatches.append((e.id, "MA", e.correction_formula, e.average_mass, round(_mass(comp, "avg"), 4)))
    assert checked > 500
    assert mismatches == []


def test_known_mismatches_still_mismatch(db: PtmDatabase) -> None:
    """If upstream fixes one of these, drop it from KNOWN_MISMATCHES."""
    for ptm_id, reason in KNOWN_MISMATCHES.items():
        e = db[ptm_id]
        assert e.monoisotopic_mass is not None
        assert abs(_mass(e.dict_composition or {}, "mono") - e.monoisotopic_mass) > MONO_TOL, reason


@pytest.mark.parametrize(
    ("ptm_id", "mono"),
    [
        ("PTM-0450", -17.026549),  # H-3 N-1
        ("PTM-0187", 43.054227),  # N6,N6,N6-trimethyllysine, C3 H7 minus one electron
    ],
)
def test_spot_values(db: PtmDatabase, ptm_id: str, mono: float) -> None:
    assert _mono(ptm_id, db[ptm_id].dict_composition or {}) == pytest.approx(mono, abs=MONO_TOL)
