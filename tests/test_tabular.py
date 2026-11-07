import csv
import dataclasses
from importlib.resources import as_file, files

from uniprotptmpy import PtmDatabase, PtmEntry, parse_ptm_list, write_tsv
from uniprotptmpy._tabular import _SUB_DELIM, _format_taxonomic_range, build_columns


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
    assert row["proforma_formula"] == "H-3N-1"
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
    assert row["keywords"].split(_SUB_DELIM) == ["Acetylation", "Methylation"]


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


def test_bundled_tsv_equals_write_tsv_output(db: PtmDatabase, tmp_path) -> None:
    from importlib.resources import files

    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    # Text mode: a Windows git checkout may give the bundled file CRLF line endings.
    bundled = files("uniprotptmpy").joinpath("data/ptmlist.tsv").read_text(encoding="utf-8")
    assert out.read_text(encoding="utf-8") == bundled


def test_no_cell_contains_the_subvalue_delimiter(db: PtmDatabase, tmp_path) -> None:
    """The multi-value separator must not occur inside any value it separates.

    This is the invariant that makes a multi-valued cell splittable at all. It held
    for neither keywords nor taxonomic ranges under the old "; " separator, because
    UniProt writes a range as "Archaea; taxId:2157 (Archaea)".
    """
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    emitted = {row["id"]: row for row in _read_dict(out)}
    for entry in db:
        row = emitted[entry.accession]
        values = (*entry.keywords, *(_format_taxonomic_range(t) for t in entry.taxonomic_ranges))
        for value in values:
            assert _SUB_DELIM not in value, f"{entry.accession}: {value!r} contains {_SUB_DELIM!r}"
        # And the emitted cells hold exactly as many separators as there are gaps.
        for column, count in (("keywords", len(entry.keywords)), ("taxonomic_ranges", len(entry.taxonomic_ranges))):
            assert row[column].count(_SUB_DELIM) == max(count - 1, 0), f"{entry.accession} {column}"


def test_multivalued_cells_split_back_into_the_same_number_of_values(db: PtmDatabase, tmp_path) -> None:
    """Splitting a cell on the separator must recover exactly the entry's values.

    A count test rather than a spot check: under "; " this failed for 54 keyword
    cells and 737 taxonomic-range cells on the bundled 2026_03 release.
    """
    out = tmp_path / "ptm.tsv"
    write_tsv(db, out)
    rows = {row["id"]: row for row in _read_dict(out)}
    assert len(rows) == len(db)
    for entry in db:
        row = rows[entry.accession]
        expected_ranges = [_format_taxonomic_range(t) for t in entry.taxonomic_ranges]
        for column, expected in (("keywords", list(entry.keywords)), ("taxonomic_ranges", expected_ranges)):
            recovered = row[column].split(_SUB_DELIM) if row[column] else []
            assert recovered == expected, f"{entry.accession} {column}: {recovered} != {expected}"


def test_no_entry_has_two_cross_references_in_one_database(db: PtmDatabase) -> None:
    """Guard for the last-wins dict in ``to_row``, which keeps one accession per database.

    One ``xref_<db>`` column per database is only lossless while no entry carries two
    cross-references in the same database. The bundled release has 1580 cross-references
    and 1580 distinct (entry, database) pairs, so this is true by data, not by
    construction. If a future release breaks it, fail here rather than silently drop an
    accession from the export.
    """
    offenders = {}
    for entry in db:
        databases = [xr.database for xr in entry.cross_references]
        duplicated = {d for d in databases if databases.count(d) > 1}
        if duplicated:
            offenders[entry.accession] = sorted(duplicated)
    assert offenders == {}, f"entries with two cross-references in one database: {offenders}"


def test_bundled_tsv_is_exactly_a_fresh_export_of_the_bundled_ptmlist(tmp_path) -> None:
    """``data/ptmlist.tsv`` must equal ``write_tsv`` of ``data/ptmlist.txt``, byte for byte.

    The separator defect shipped in that artifact because nothing compared it to its source:
    it is bundled, nothing reads it and no script regenerates it, so it went stale silently and
    a release carried the wrong separator. Asserting the artifact against a fresh export is what
    makes a stale copy a test failure instead of a shipped defect. Found and first measured by
    psimodpy, which exported a fresh TSV independently and matched the header and 750 of 750 rows.
    """
    committed = files("uniprotptmpy") / "data" / "ptmlist.tsv"
    fresh = tmp_path / "fresh.tsv"
    with as_file(files("uniprotptmpy") / "data" / "ptmlist.txt") as source:
        write_tsv(parse_ptm_list(source), fresh)

    expected = committed.read_text(encoding="utf-8").splitlines()
    actual = fresh.read_text(encoding="utf-8").splitlines()
    assert actual[0] == expected[0], "header differs"
    assert len(actual) == len(expected), f"{len(actual)} rows exported, {len(expected)} committed"
    differing = [i for i, (a, e) in enumerate(zip(actual, expected, strict=True)) if a != e]
    assert differing == [], (
        f"{len(differing)} of {len(expected) - 1} rows differ from a fresh export; "
        f"regenerate with load().write_tsv(). First at line {differing[0] + 1 if differing else 0}"
    )


def test_exported_multivalue_parts_equal_parsed_parts(db: PtmDatabase, tmp_path) -> None:
    """Splitting the whole export recovers as many parts as the parser produced, column by column.

    The separator is only correct while no value contains it. ``test_bundled_tsv_...`` catches a
    stale artifact but not that, because a value carrying ``" | "`` would shred identically on
    both sides. This counts instead: 1021 taxonomic-range parts and 558 keyword parts in the
    bundled 2026_03 release, and a value containing the separator makes the export yield more
    than the parser did. Asserted against the parsed total rather than against a number written
    down here, so a UniProt update moves both sides and this does not go stale. Asked for by
    psimodpy, whose #65 asserts the same for synonyms.
    """
    path = write_tsv(db, tmp_path / "counts.tsv")
    rows = _read_dict(path)
    for column, parsed in (
        ("taxonomic_ranges", sum(len(e.taxonomic_ranges) for e in db)),
        ("keywords", sum(len(e.keywords) for e in db)),
    ):
        exported = sum(len(row[column].split(_SUB_DELIM)) for row in rows if row[column])
        assert exported == parsed, f"{column}: export yields {exported} parts, parser produced {parsed}"


# Fields exported as one ``_SUB_DELIM``-joined cell, and therefore covered by the
# delimiter and round-trip guards above.
_JOINED_FIELDS = frozenset({"keywords", "taxonomic_ranges"})
# Multi-valued fields deliberately exported some other way. ``cross_references`` gets one
# ``xref_<database>`` column each, guarded by its own last-wins test.
_UNJOINED_FIELDS = frozenset({"cross_references"})


def test_every_multivalued_field_is_joined_or_deliberately_exempt() -> None:
    """A new multi-valued field must not escape the delimiter guards by being added quietly.

    The guards above name their two columns by hand, so their scope cannot grow with the
    code: a third joined column would be exported unchecked and nothing would say so. This
    fails instead, forcing the choice between joining it (and adding it to ``_JOINED_FIELDS``,
    which puts it under those guards) and exporting it some other way (and saying so in
    ``_UNJOINED_FIELDS``).
    """
    multivalued = {f.name for f in dataclasses.fields(PtmEntry) if str(f.type).startswith("tuple[")}
    assert multivalued == _JOINED_FIELDS | _UNJOINED_FIELDS, (
        f"multi-valued fields are {sorted(multivalued)}; "
        f"joined {sorted(_JOINED_FIELDS)} plus exempt {sorted(_UNJOINED_FIELDS)}. "
        "Add the new field to one of the two sets."
    )


def test_no_column_outside_the_joined_set_carries_the_separator(db: PtmDatabase, tmp_path) -> None:
    """The field-level set above, checked against a real export rather than against the source.

    A subset and not an equality: in the bundled release 197 entries have more than one
    taxonomic range but only 1 has more than one keyword, so equality would fail the day a
    UniProt update left every entry with a single keyword, which is not a defect. What is a
    defect is any other column carrying the separator, and that is what this forbids.
    """
    path = write_tsv(db, tmp_path / "columns.tsv")
    carrying = {column for row in _read_dict(path) for column, cell in row.items() if cell and _SUB_DELIM in cell}
    escaped = sorted(carrying - _JOINED_FIELDS)
    assert not escaped, f"columns outside {sorted(_JOINED_FIELDS)} carry {_SUB_DELIM!r}: {escaped}"
