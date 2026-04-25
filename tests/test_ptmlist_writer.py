"""Tests for the ptmlist.txt round-trip writer."""

from uniprotptmpy import PtmDatabase, load, parse_ptm_list, write_ptmlist


def test_write_produces_file(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_round_trip_entry_count(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    assert len(db2) == len(db)


def test_round_trip_name(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.name == e2.name


def test_round_trip_feature_type(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.feature_type == e2.feature_type


def test_round_trip_target(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.target == e2.target


def test_round_trip_correction_formula(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.correction_formula == e2.correction_formula


def test_round_trip_masses(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.monoisotopic_mass == e2.monoisotopic_mass
    assert e1.average_mass == e2.average_mass


def test_round_trip_optional_fields(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert e1.amino_acid_position == e2.amino_acid_position
    assert e1.polypeptide_position == e2.polypeptide_position
    assert e1.cellular_location == e2.cellular_location


def test_round_trip_taxonomic_ranges(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert len(e1.taxonomic_ranges) == len(e2.taxonomic_ranges)
    names1 = {tr.taxon_name for tr in e1.taxonomic_ranges}
    names2 = {tr.taxon_name for tr in e2.taxonomic_ranges}
    assert names1 == names2


def test_round_trip_keywords(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    # Find an entry with keywords
    e1 = next(e for e in db if e.keywords)
    e2 = db2.get_by_id(e1.id)
    assert e2 is not None
    assert set(e1.keywords) == set(e2.keywords)


def test_round_trip_cross_references(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    db2 = parse_ptm_list(out)
    e1 = db["PTM-0450"]
    e2 = db2["PTM-0450"]
    assert len(e1.cross_references) == len(e2.cross_references)
    xr1 = {(xr.database, xr.accession) for xr in e1.cross_references}
    xr2 = {(xr.database, xr.accession) for xr in e2.cross_references}
    assert xr1 == xr2


def test_proforma_formula_not_written(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    write_ptmlist(db, out)
    content = out.read_text(encoding="utf-8")
    # PF is not a valid ptmlist line code — should never appear
    assert "\nPF   " not in content


def test_creates_parent_directory(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "nested" / "out.txt"
    write_ptmlist(db, out)
    assert out.exists()


def test_database_method_returns_path(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    result = db.write_ptmlist(out)
    assert result == out
    assert out.exists()


def test_database_method_round_trip(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "out.txt"
    db.write_ptmlist(out)
    db2 = parse_ptm_list(out)
    assert len(db2) == len(db)
