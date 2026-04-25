"""Writer for UniProt ptmlist.txt flat-file format."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from uniprotptmpy.models import PtmEntry, TaxonomicRange


def _fmt_line(code: str, value: str) -> str:
    return f"{code}   {value}\n"


def _format_tr(tr: TaxonomicRange) -> str:
    if tr.raw:
        return tr.raw
    if tr.tax_id is not None:
        return f"{tr.taxon_name}; taxId:{tr.tax_id}"
    return tr.taxon_name


def _write_entry(fh, entry: PtmEntry) -> None:
    fh.write(_fmt_line("ID", entry.name))
    fh.write(_fmt_line("AC", entry.id))
    fh.write(_fmt_line("FT", str(entry.feature_type)))
    fh.write(_fmt_line("TG", entry.target + "."))
    if entry.amino_acid_position is not None:
        fh.write(_fmt_line("PA", entry.amino_acid_position + "."))
    if entry.polypeptide_position is not None:
        fh.write(_fmt_line("PP", entry.polypeptide_position + "."))
    if entry.correction_formula is not None:
        fh.write(_fmt_line("CF", entry.correction_formula))
    if entry.monoisotopic_mass is not None:
        fh.write(_fmt_line("MM", str(entry.monoisotopic_mass)))
    if entry.average_mass is not None:
        fh.write(_fmt_line("MA", str(entry.average_mass)))
    if entry.cellular_location is not None:
        fh.write(_fmt_line("LC", entry.cellular_location + "."))
    for tr in entry.taxonomic_ranges:
        fh.write(_fmt_line("TR", _format_tr(tr)))
    for kw in entry.keywords:
        fh.write(_fmt_line("KW", kw + "."))
    for xr in entry.cross_references:
        fh.write(_fmt_line("DR", f"{xr.database}; {xr.accession}."))
    fh.write("//\n")


def write_ptmlist(entries: Iterable[PtmEntry], path: Path | str) -> Path:
    """Write PTM entries to a ptmlist.txt-format flat file.

    The output is suitable for re-parsing with parse_ptm_list(). Returns the
    resolved Path.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for entry in entries:
            _write_entry(fh, entry)
    return out
