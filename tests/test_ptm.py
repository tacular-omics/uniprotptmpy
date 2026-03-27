import dataclasses

import pytest

from uniprotptmpy import CrossReference, FeatureType, PtmDatabase, PtmEntry, load, parse_ptm_list


# --- Entry count ---


def test_entry_count(db: PtmDatabase) -> None:
    assert len(db) == 748


# --- Scalar field parsing (PTM-0450 is the "full fields" anchor) ---


def test_full_entry_name(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.name == "(2-aminosuccinimidyl)acetic acid (Asn-Gly)"


def test_full_entry_feature_type(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.feature_type == FeatureType.CROSSLNK


def test_full_entry_target(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.target == "Asparagine-Glycine"


def test_full_entry_amino_acid_position(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.amino_acid_position == "Amino acid side chain-Amino acid backbone"


def test_full_entry_polypeptide_position(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.polypeptide_position == "Anywhere-Protein core"


def test_full_entry_correction_formula(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.correction_formula == "H-3 N-1"


def test_full_entry_monoisotopic_mass(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.monoisotopic_mass == pytest.approx(-17.026549)


def test_full_entry_average_mass(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.average_mass == pytest.approx(-17.03)


def test_full_entry_cellular_location(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert e.cellular_location == "Extracellular and lumenal localisation"


# --- Optional fields absent (PTM-0058 "Alanine derivative") ---


def test_optional_cf_absent(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.correction_formula is None


def test_optional_mm_absent(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.monoisotopic_mass is None


def test_optional_ma_absent(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.average_mass is None


def test_optional_pa_absent(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.amino_acid_position is None


def test_optional_pp_absent(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.polypeptide_position is None


# --- Multi-value fields ---


def test_taxonomic_ranges_count(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    assert len(e.taxonomic_ranges) == 3


def test_taxonomic_range_taxon_name(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    tr = e.taxonomic_ranges[0]
    assert tr.taxon_name == "Archaea"


def test_taxonomic_range_tax_id(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    tr = e.taxonomic_ranges[0]
    assert tr.tax_id == 2157


def test_taxonomic_range_description(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    tr = e.taxonomic_ranges[0]
    assert tr.description == "Archaea"


def test_single_keyword(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0476")
    assert e is not None
    assert "Hydroxylation" in e.keywords


def test_multiple_keywords(db: PtmDatabase) -> None:
    e = db.get_by_name("N6-acetyl-N6-methyllysine")
    assert e is not None
    assert "Acetylation" in e.keywords
    assert "Methylation" in e.keywords
    assert len(e.keywords) == 2


def test_cross_references_databases(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    dbs = {xr.database for xr in e.cross_references}
    assert "RESID" in dbs
    assert "PSI-MOD" in dbs


def test_cross_reference_accession_stripped(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    resid = next(xr for xr in e.cross_references if xr.database == "RESID")
    assert resid.accession == "AA0441"


def test_no_cross_references(db: PtmDatabase) -> None:
    entries_no_dr = [e for e in db if len(e.cross_references) == 0]
    assert len(entries_no_dr) > 0


# --- Formula / composition ---


def test_dict_composition_positive(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0476")
    assert e is not None
    assert e.dict_composition == {"O": 1}


def test_dict_composition_negative(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    comp = e.dict_composition
    assert comp is not None
    assert comp["H"] == -3
    assert comp["N"] == -1


def test_dict_composition_none_when_no_cf(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.dict_composition is None


def test_proforma_formula_single_element(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0476")
    assert e is not None
    assert e.proforma_formula == "O"


def test_proforma_formula_none_when_no_cf(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0058")
    assert e is not None
    assert e.proforma_formula is None


# --- Database lookups ---


def test_get_by_id_full_string(db: PtmDatabase) -> None:
    assert db.get_by_id("PTM-0450") is not None


def test_get_by_id_bare_number(db: PtmDatabase) -> None:
    assert db.get_by_id("0450") is not None


def test_get_by_id_missing(db: PtmDatabase) -> None:
    assert db.get_by_id("PTM-9999") is None


def test_get_by_id_invalid(db: PtmDatabase) -> None:
    assert db.get_by_id("not_an_id") is None


def test_get_by_name_exact(db: PtmDatabase) -> None:
    assert db.get_by_name("(3R)-3-hydroxyarginine") is not None


def test_get_by_name_case_insensitive(db: PtmDatabase) -> None:
    assert db.get_by_name("(3r)-3-HYDROXYARGININE") is not None


def test_get_by_name_missing(db: PtmDatabase) -> None:
    assert db.get_by_name("nonexistent_xyz_abc") is None


def test_getitem_by_id(db: PtmDatabase) -> None:
    assert db["PTM-0450"] is not None


def test_getitem_raises_keyerror(db: PtmDatabase) -> None:
    with pytest.raises(KeyError):
        _ = db["PTM-9999"]


# --- Search ---


def test_search_by_name_substring(db: PtmDatabase) -> None:
    results = db.search("hydroxylation")
    assert len(results) > 0


def test_search_by_target(db: PtmDatabase) -> None:
    results = db.search("Arginine")
    assert any(e.target == "Arginine" for e in results)


def test_search_empty_returns_all(db: PtmDatabase) -> None:
    assert len(db.search("")) == len(db)


def test_search_no_match(db: PtmDatabase) -> None:
    assert db.search("xyzzy_no_match_ever") == []


# --- Immutability ---


def test_entry_is_frozen(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        e.name = "mutated"  # type: ignore[misc]


def test_cross_reference_is_frozen(db: PtmDatabase) -> None:
    e = db.get_by_id("PTM-0450")
    assert e is not None
    xr = e.cross_references[0]
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        xr.database = "mutated"  # type: ignore[misc]


# --- Iteration ---


def test_iter_all_entries(db: PtmDatabase) -> None:
    entries = list(db)
    assert len(entries) == len(db)


def test_all_entries_have_valid_id(db: PtmDatabase) -> None:
    for e in db:
        assert isinstance(e.id, str)
        assert e.id.startswith("PTM-")


def test_all_entries_have_nonempty_name(db: PtmDatabase) -> None:
    for e in db:
        assert isinstance(e.name, str)
        assert len(e.name) > 0


# --- parse_ptm_list with minimal fixture ---


def test_parse_minimal(tmp_path):
    data = tmp_path / "mini.txt"
    data.write_text(
        "ID   Test mod\nAC   PTM-0001\nFT   MOD_RES\nTG   Alanine.\n"
        "MM   15.994915\nMA   16.00\n//\n",
        encoding="utf-8",
    )
    result = parse_ptm_list(data)
    assert len(result) == 1
    e = result["PTM-0001"]
    assert e.name == "Test mod"
    assert e.monoisotopic_mass == pytest.approx(15.994915)
    assert e.correction_formula is None
    assert e.amino_acid_position is None
