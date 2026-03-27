from __future__ import annotations

import pytest

from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.models import CrossReference, FeatureType, PtmEntry, TaxonomicRange


def _make_entry(
    id: str = "PTM-0001",
    name: str = "Test mod",
    *,
    target: str = "Alanine",
    keywords: tuple[str, ...] = (),
) -> PtmEntry:
    return PtmEntry(
        id=id,
        name=name,
        feature_type=FeatureType.MOD_RES,
        target=target,
        amino_acid_position=None,
        polypeptide_position=None,
        correction_formula=None,
        monoisotopic_mass=None,
        average_mass=None,
        cellular_location=None,
        taxonomic_ranges=(),
        keywords=keywords,
        cross_references=(),
    )


def test_empty_database() -> None:
    db = PtmDatabase([])
    assert len(db) == 0
    assert list(db) == []
    assert db.get_by_id("PTM-0001") is None
    assert db.get_by_name("anything") is None
    assert db.search("anything") == []


def test_getitem_by_name_fallback() -> None:
    """__getitem__ falls back to name lookup when ID lookup fails."""
    entry = _make_entry(name="Phosphoserine")
    db = PtmDatabase([entry])
    assert db["Phosphoserine"] is entry


def test_getitem_raises_keyerror() -> None:
    db = PtmDatabase([])
    with pytest.raises(KeyError):
        _ = db["PTM-9999"]


def test_search_matches_keyword() -> None:
    entry = _make_entry(keywords=("Acetylation", "Methylation"))
    db = PtmDatabase([entry])
    assert db.search("acetylation") == [entry]
    assert db.search("methylation") == [entry]
    assert db.search("phospho") == []


def test_len() -> None:
    entries = [_make_entry(id=f"PTM-{i:04d}", name=f"Mod {i}") for i in range(5)]
    db = PtmDatabase(entries)
    assert len(db) == 5


def test_iter_preserves_order() -> None:
    entries = [_make_entry(id=f"PTM-{i:04d}", name=f"Mod {i}") for i in range(3)]
    db = PtmDatabase(entries)
    assert list(db) == entries
