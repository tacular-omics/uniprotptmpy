import csv

from uniprotptmpy import PtmDatabase, write_tsv
from uniprotptmpy._tabular import COLUMNS


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
    assert tuple(rows[0]) == COLUMNS


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
    # No "None" literal anywhere.
    assert "None" not in row.values()


def test_keywords_joined(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["name"] == "N6-acetyl-N6-methyllysine")
    assert "Acetylation" in row["keywords"]
    assert "Methylation" in row["keywords"]
    assert "; " in row["keywords"]


def test_cross_references_formatted(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    parts = row["cross_references"].split("; ")
    assert "RESID:AA0441" in parts
    assert any(p.startswith("PSI-MOD:") for p in parts)


def test_taxonomic_ranges_formatted(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    row = next(r for r in rows if r["id"] == "PTM-0450")
    parts = row["taxonomic_ranges"].split("; taxId:")
    assert "Archaea" in parts[0]


def test_empty_collections_render_empty(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = _read_dict(out)
    no_dr_id = next(e.id for e in db if not e.cross_references)
    row = next(r for r in rows if r["id"] == no_dr_id)
    assert row["cross_references"] == ""


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


def test_creates_parent_directory(db: PtmDatabase, tmp_path) -> None:
    out = tmp_path / "nested" / "dir" / "ptm.tsv"
    write_tsv(db, out)
    assert out.exists()
