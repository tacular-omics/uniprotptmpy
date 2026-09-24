from __future__ import annotations

import pytest

from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.models import FeatureType, PtmEntry


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


def test_contains_accepts_every_getitem_key_form() -> None:
    """``in`` agrees with ``__getitem__``: full id, bare id, any-case id and name."""
    entry = _make_entry(id="PTM-0450", name="Phosphoserine")
    db = PtmDatabase([entry])
    for key in ("PTM-0450", "ptm-0450", "0450", "Phosphoserine", "PHOSPHOSERINE"):
        assert key in db
        assert db[key] is entry
    assert "PTM-9999" not in db
    assert "nonexistent" not in db


def test_contains_non_string_returns_false() -> None:
    db = PtmDatabase([_make_entry()])
    assert 450 not in db
    assert None not in db


def test_contains_entry_object() -> None:
    """Membership by entry object still works, as it did via iteration."""
    entry = _make_entry()
    db = PtmDatabase([entry])
    assert entry in db
    assert _make_entry(id="PTM-0002", name="Other") not in db


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


# ---------------------------------------------------------------------------
# Uniform lookup: [] / get / in agree, and match psimodpy and unimodpy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["PTM-0450", "ptm-0450", "0450", "450", 450, "PTM-450", "PTM-00450", " PTM-0450 "])
def test_bundled_get_accepts_every_id_form(key: object) -> None:
    from uniprotptmpy import load

    db = load()
    assert db.get(key) is db["PTM-0450"]
    assert key in db


@pytest.mark.parametrize("key", ["PTM-9999", "PTM-abc", "foo", "", None, 450.0, -1, ("PTM-0001",), ["PTM-0001"]])
def test_get_missing_or_malformed_returns_default(key: object) -> None:
    db = PtmDatabase([_make_entry("PTM-0001", "Test mod")])
    assert db.get(key) is None
    sentinel = object()
    assert db.get(key, sentinel) is sentinel
    assert key not in db
    with pytest.raises(KeyError):
        db[key]  # ty: ignore[invalid-argument-type]


def test_get_by_id_int_and_unpadded() -> None:
    db = PtmDatabase([_make_entry("PTM-0001", "Test mod")])
    assert db.get_by_id(1) is db["PTM-0001"]
    assert db.get_by_id("1") is db["PTM-0001"]
    assert db.get_by_id(1.0) is None  # ty: ignore[invalid-argument-type]
    assert db.get_by_id(None) is None  # ty: ignore[invalid-argument-type]


def test_get_by_name() -> None:
    db = PtmDatabase([_make_entry("PTM-0001", "Test mod")])
    assert db.get("TEST MOD") is db["PTM-0001"]
