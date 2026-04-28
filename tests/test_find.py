from __future__ import annotations

import pytest

from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.models import CrossReference, FeatureType, PtmEntry, TaxonomicRange


def _make_entry(
    id: str = "PTM-0001",
    name: str = "Test mod",
    *,
    feature_type: FeatureType = FeatureType.MOD_RES,
    target: str = "Alanine",
    monoisotopic_mass: float | None = None,
    average_mass: float | None = None,
    keywords: tuple[str, ...] = (),
    taxonomic_ranges: tuple[TaxonomicRange, ...] = (),
    cross_references: tuple[CrossReference, ...] = (),
) -> PtmEntry:
    return PtmEntry(
        id=id,
        name=name,
        feature_type=feature_type,
        target=target,
        amino_acid_position=None,
        polypeptide_position=None,
        correction_formula=None,
        monoisotopic_mass=monoisotopic_mass,
        average_mass=average_mass,
        cellular_location=None,
        taxonomic_ranges=taxonomic_ranges,
        keywords=keywords,
        cross_references=cross_references,
    )


@pytest.fixture()
def db() -> PtmDatabase:
    entries = [
        _make_entry(
            id="PTM-0001",
            name="Phosphoserine",
            feature_type=FeatureType.MOD_RES,
            target="Serine",
            monoisotopic_mass=79.9663,
            average_mass=80.00,
            keywords=("Phosphoprotein",),
            taxonomic_ranges=(
                TaxonomicRange(taxon_name="Eukaryota", tax_id=2759, description="", raw=""),
            ),
        ),
        _make_entry(
            id="PTM-0002",
            name="Phosphothreonine",
            feature_type=FeatureType.MOD_RES,
            target="Threonine",
            monoisotopic_mass=79.9663,
            average_mass=80.00,
            keywords=("Phosphoprotein",),
            taxonomic_ranges=(
                TaxonomicRange(taxon_name="Bacteria", tax_id=2, description="", raw=""),
            ),
        ),
        _make_entry(
            id="PTM-0003",
            name="N-acetylalanine",
            feature_type=FeatureType.MOD_RES,
            target="Alanine",
            monoisotopic_mass=42.0106,
            average_mass=42.04,
            keywords=("Acetylation",),
        ),
        _make_entry(
            id="PTM-0004",
            name="S-palmitoyl cysteine",
            feature_type=FeatureType.LIPID,
            target="Cysteine",
            monoisotopic_mass=238.2297,
            average_mass=238.41,
            keywords=("Lipoprotein", "Palmitate"),
        ),
        _make_entry(
            id="PTM-0005",
            name="Glycopeptide",
            feature_type=FeatureType.CARBOHYD,
            target="",
            monoisotopic_mass=None,
            average_mass=None,
            keywords=("Glycoprotein",),
        ),
    ]
    return PtmDatabase(entries)


def test_find_no_filters_returns_all(db: PtmDatabase) -> None:
    assert len(db.find()) == 5


def test_find_mass_range_mono(db: PtmDatabase) -> None:
    results = db.find(mass_min=40.0, mass_max=100.0)
    ids = {e.id for e in results}
    assert ids == {"PTM-0001", "PTM-0002", "PTM-0003"}


def test_find_mass_range_avg(db: PtmDatabase) -> None:
    results = db.find(mass_min=200.0, mass_type="avg")
    assert [e.id for e in results] == ["PTM-0004"]


def test_find_mass_skips_none(db: PtmDatabase) -> None:
    results = db.find(mass_min=0.0)
    assert all(e.id != "PTM-0005" for e in results)


def test_find_residues_single(db: PtmDatabase) -> None:
    results = db.find(residues=["serine"])
    assert [e.id for e in results] == ["PTM-0001"]


def test_find_residues_multi_case_insensitive(db: PtmDatabase) -> None:
    results = db.find(residues=["SERINE", "Threonine"])
    assert {e.id for e in results} == {"PTM-0001", "PTM-0002"}


def test_find_residues_skips_empty_target(db: PtmDatabase) -> None:
    results = db.find(residues=["alanine"])
    assert {e.id for e in results} == {"PTM-0003"}


def test_find_feature_type_string(db: PtmDatabase) -> None:
    results = db.find(feature_type="LIPID")
    assert [e.id for e in results] == ["PTM-0004"]


def test_find_feature_type_invalid_returns_empty(db: PtmDatabase) -> None:
    assert db.find(feature_type="NOPE") == []


def test_find_keyword_case_insensitive(db: PtmDatabase) -> None:
    results = db.find(keyword="phosphoprotein")
    assert {e.id for e in results} == {"PTM-0001", "PTM-0002"}


def test_find_taxon_id(db: PtmDatabase) -> None:
    results = db.find(taxon_id=2)
    assert [e.id for e in results] == ["PTM-0002"]


def test_find_text_and_residues_combined(db: PtmDatabase) -> None:
    results = db.find(text="phospho", residues=["serine"])
    assert [e.id for e in results] == ["PTM-0001"]


def test_find_limit(db: PtmDatabase) -> None:
    results = db.find(keyword="phosphoprotein", limit=1)
    assert len(results) == 1


def test_find_and_combination_excludes(db: PtmDatabase) -> None:
    # Phospho text matches PTM-0001/0002 but residues=cysteine excludes both.
    results = db.find(text="phospho", residues=["cysteine"])
    assert results == []
