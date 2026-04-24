"""Tabular (TSV/CSV) writer for PTM entries."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from uniprotptmpy.models import CrossReference, PtmEntry, TaxonomicRange

COLUMNS: tuple[str, ...] = (
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
    "cross_references",
    "taxonomic_ranges",
)

_SUB_DELIM = "; "


def _format_cross_reference(ref: CrossReference) -> str:
    return f"{ref.database}:{ref.accession}"


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


def to_row(entry: PtmEntry) -> list[str]:
    """Flatten a PtmEntry to the documented column order."""
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
        _SUB_DELIM.join(_format_cross_reference(r) for r in entry.cross_references),
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
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=delimiter, lineterminator="\n")
        writer.writerow(COLUMNS)
        for entry in entries:
            writer.writerow(to_row(entry))
    return out
