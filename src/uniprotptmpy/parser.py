"""Parser for UniProt ptmlist.txt flat-file format."""

from __future__ import annotations

import re
from importlib.resources import as_file, files
from pathlib import Path

from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.models import CrossReference, FeatureType, PtmEntry, TaxonomicRange

_MULTI_VALUE = {"TR", "KW", "DR"}
_TR_TAXID_RE = re.compile(r"taxId:(\d+)")
_TR_DESC_RE = re.compile(r"\((.+?)\)")


def _strip_period(s: str) -> str:
    return s.rstrip(".")


def _parse_tr(raw: str) -> TaxonomicRange:
    raw_clean = _strip_period(raw)
    if "; taxId:" in raw_clean:
        taxon_name, rest = raw_clean.split("; taxId:", 1)
        taxid_match = re.match(r"(\d+)", rest)
        tax_id = int(taxid_match.group(1)) if taxid_match else None
    else:
        taxon_name = raw_clean
        tax_id = None
    desc_match = _TR_DESC_RE.search(raw_clean)
    description = desc_match.group(1) if desc_match else ""
    return TaxonomicRange(taxon_name=taxon_name, tax_id=tax_id, description=description, raw=raw_clean)


def _parse_dr(raw: str) -> CrossReference:
    raw_clean = _strip_period(raw)
    if "; " in raw_clean:
        database, accession = raw_clean.split("; ", 1)
    else:
        database, accession = raw_clean, ""
    return CrossReference(database=database, accession=accession)


def _build_entry(fields: dict) -> PtmEntry:
    return PtmEntry(
        id=fields["AC"],
        name=fields["ID"],
        feature_type=FeatureType(fields["FT"]),
        target=_strip_period(fields["TG"]),
        amino_acid_position=_strip_period(fields["PA"]) if "PA" in fields else None,
        polypeptide_position=_strip_period(fields["PP"]) if "PP" in fields else None,
        correction_formula=fields.get("CF"),
        monoisotopic_mass=float(fields["MM"]) if "MM" in fields else None,
        average_mass=float(fields["MA"]) if "MA" in fields else None,
        cellular_location=_strip_period(fields["LC"]) if "LC" in fields else None,
        taxonomic_ranges=tuple(_parse_tr(v) for v in fields.get("TR", [])),
        keywords=tuple(_strip_period(v) for v in fields.get("KW", [])),
        cross_references=tuple(_parse_dr(v) for v in fields.get("DR", [])),
    )


def parse_ptm_list(path: Path | str) -> PtmDatabase:
    """Parse a ptmlist.txt file into a PtmDatabase."""
    path = Path(path)
    entries: list[PtmEntry] = []
    in_entry = False
    current_fields: dict = {}

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if len(line) < 2:
                continue
            code = line[:2]
            value = line[5:] if len(line) > 5 else ""

            if code == "ID":
                in_entry = True
                current_fields = {"ID": value}
            elif code == "//" and in_entry:
                entries.append(_build_entry(current_fields))
                in_entry = False
                current_fields = {}
            elif in_entry:
                if code in _MULTI_VALUE:
                    current_fields.setdefault(code, []).append(value)
                elif code.strip():
                    current_fields[code] = value

    return PtmDatabase(entries)


def load(source: Path | str | None = None) -> PtmDatabase:
    """Load the PTM database. Uses the bundled ptmlist.txt by default."""
    if source is not None:
        return parse_ptm_list(source)
    ref = files("uniprotptmpy") / "data" / "ptmlist.txt"
    with as_file(ref) as path:
        return parse_ptm_list(path)
