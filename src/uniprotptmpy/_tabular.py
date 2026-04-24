"""Tabular (TSV/CSV) writer for PTM entries."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from uniprotptmpy.models import PtmEntry, TaxonomicRange

_FIXED_PREFIX: tuple[str, ...] = (
    "id",
    "name",
    "feature_type",
    "target",
    "amino_acid_position",
    "polypeptide_position",
    "correction_formula",
    "proforma_formula",
    "monoisotopic_mass",
    "average_mass",
    "cellular_location",
    "keywords",
)
_FIXED_SUFFIX: tuple[str, ...] = ("taxonomic_ranges",)

_SUB_DELIM = "; "


def _xref_column(database: str) -> str:
    """Sanitize an xref database name into a column header (e.g. 'PSI-MOD' -> 'xref_psi_mod')."""
    return "xref_" + database.lower().replace("-", "_")


def _xref_databases(entries: Iterable[PtmEntry]) -> list[str]:
    """Return the sorted set of cross-reference database names present in entries."""
    return sorted({xr.database for e in entries for xr in e.cross_references})


def build_columns(entries: Iterable[PtmEntry]) -> tuple[str, ...]:
    """Build the full TSV column header for the given entries.

    Adds one ``xref_<database>`` column per cross-reference database actually
    present, sorted alphabetically.
    """
    xref_cols = tuple(_xref_column(db) for db in _xref_databases(entries))
    return _FIXED_PREFIX + xref_cols + _FIXED_SUFFIX


def _format_taxonomic_range(tr: TaxonomicRange) -> str:
    if tr.raw:
        return tr.raw
    if tr.tax_id is not None:
        return f"{tr.taxon_name}; taxId:{tr.tax_id}"
    return tr.taxon_name


def _cell(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def to_row(entry: PtmEntry, xref_databases: list[str]) -> list[str]:
    """Flatten a PtmEntry, with one cell per database in ``xref_databases``."""
    xref_by_db = {xr.database: xr.accession for xr in entry.cross_references}
    return [
        entry.id,
        entry.name,
        str(entry.feature_type),
        entry.target,
        _cell(entry.amino_acid_position),
        _cell(entry.polypeptide_position),
        _cell(entry.correction_formula),
        _cell(entry.proforma_formula),
        _cell(entry.monoisotopic_mass),
        _cell(entry.average_mass),
        _cell(entry.cellular_location),
        _SUB_DELIM.join(entry.keywords),
        *(xref_by_db.get(db, "") for db in xref_databases),
        _SUB_DELIM.join(_format_taxonomic_range(t) for t in entry.taxonomic_ranges),
    ]


def write_tsv(
    entries: Iterable[PtmEntry],
    path: Path | str,
    *,
    delimiter: str = "\t",
) -> Path:
    """Write PTM entries to a tab-separated file.

    Pass ``delimiter=","`` to emit CSV instead. Returns the resolved Path.
    """
    materialized = list(entries)
    xref_dbs = _xref_databases(materialized)
    header = _FIXED_PREFIX + tuple(_xref_column(db) for db in xref_dbs) + _FIXED_SUFFIX

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=delimiter, lineterminator="\n")
        writer.writerow(header)
        for entry in materialized:
            writer.writerow(to_row(entry, xref_dbs))
    return out
