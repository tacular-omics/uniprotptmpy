import csv

from uniprotptmpy import PtmDatabase, write_tsv
from uniprotptmpy._tabular import build_columns


def _read(path, delimiter="\t"):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh, delimiter=delimiter))


def _read_dict(path, delimiter="\t"):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def test_header_matches_columns(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read(out)
    assert tuple(rows[0]) == build_columns(db)


def test_header_has_one_column_per_xref_database(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    header = _read(out)[0]
    # Bundled data has these four databases.
    for col in ("xref_chebi", "xref_psi_mod", "xref_resid", "xref_unimod"):
        assert col in header
    # The legacy combined column is gone.
    assert "cross_references" not in header


def test_row_count_matches_db(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read(out)
    assert len(rows) == len(db) + 1


def test_full_entry_row(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    assert row["name"] == "(2-aminosuccinimidyl)acetic acid (Asn-Gly)"
    assert row["feature_type"] == "CROSSLNK"
    assert row["target"] == "Asparagine-Glycine"
    assert row["correction_formula"] == "H-3 N-1"
    assert row["proforma_formula"] == "H-3 N-1"
    assert float(row["monoisotopic_mass"]) == -17.026549
    assert float(row["average_mass"]) == -17.03


def test_optional_fields_render_empty(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0058")
    assert row["correction_formula"] == ""
    assert row["proforma_formula"] == ""
    assert row["monoisotopic_mass"] == ""
    assert row["average_mass"] == ""
    assert row["amino_acid_position"] == ""
    assert row["polypeptide_position"] == ""
    assert "None" not in row.values()


def test_keywords_joined(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["name"] == "N6-acetyl-N6-methyllysine")
    assert "Acetylation" in row["keywords"]
    assert "Methylation" in row["keywords"]
    assert "; " in row["keywords"]


def test_xref_columns_split_by_database(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    assert row["xref_resid"] == "AA0441"
    assert row["xref_psi_mod"] == "MOD:01624"


def test_xref_cell_empty_when_db_absent(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    # PTM-0450 has RESID and PSI-MOD but no Unimod or ChEBI.
    row = next(r for r in rows if r["id"] == "PTM-0450")
    assert row["xref_unimod"] == ""
    assert row["xref_chebi"] == ""


def test_taxonomic_ranges_formatted(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    parts = row["taxonomic_ranges"].split("; taxId:")
    assert "Archaea" in parts[0]


def test_csv_delimiter(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.csv"
    write_tsv(db, out, delimiter=",")
    rows = _read_dict(out, delimiter=",")
    assert len(rows) == len(db)
    assert any(r["id"] == "PTM-0450" for r in rows)


def test_database_method_round_trip(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    returned = db.write_tsv(out)
    assert returned == out
    rows = _read_dict(out)
    assert len(rows) == len(db)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    assert row["target"] == "Asparagine-Glycine"
    assert row["xref_resid"] == "AA0441"


def test_creates_parent_directory(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "nested" / "dir" / "ptm.tsv"
    write_tsv(db, out)
    assert out.exists()


def test_only_databases_present_get_columns(tmp_path) -> None:
    # Build a minimal db with just one xref database and verify only that
    # column appears.
    from uniprotptmpy import parse_ptm_list

    src = tmp_path / "mini.txt"
    src.write_text(
        "ID   Test mod\nAC   PTM-0001\nFT   MOD_RES\nTG   Alanine.\nDR   Unimod; 9999.\n//\n",
        encoding="utf-8",
    )
    out = tmp_path / "mini.tsv"
    write_tsv(parse_ptm_list(src), out)
    header = _read(out)[0]
    assert "xref_unimod" in header
    assert "xref_resid" not in header
    assert "xref_psi_mod" not in header
