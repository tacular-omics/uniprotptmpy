"""Parser for UniProt ptmlist.txt flat-file format."""

from __future__ import annotations

import re
import warnings
from importlib.resources import as_file, files
from pathlib import Path

from uniprotptmpy._download import download
from uniprotptmpy._formula import parse_ptm_formula
from uniprotptmpy.database import PtmDatabase
from uniprotptmpy.errors import UniprotPtmError, UniprotPtmParseError
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


def _feature_type(raw: str, where: str) -> FeatureType | str:
    try:
        return FeatureType(raw)
    except ValueError:
        warnings.warn(f"{where}: unknown feature type FT {raw!r}; kept as a plain string", stacklevel=4)
        return raw


def _float(fields: dict, code: str, where: str) -> float | None:
    if code not in fields:
        return None
    try:
        return float(fields[code])
    except ValueError:
        raise UniprotPtmParseError(f"{where}: {code} {fields[code]!r} is not a number") from None


def _build_entry(fields: dict, start_line: int, path: Path) -> PtmEntry | None:
    """Build one entry; None (with a warning) if the block lacks AC, ID, FT or TG."""
    ac = fields.get("AC", "").strip()
    name = fields.get("ID", "").strip()
    where = f"{path.name} line {start_line} ({ac or name or 'entry'})"
    missing = [code for code, value in (("AC", ac), ("ID", name)) if not value]
    missing += [code for code in ("FT", "TG") if not fields.get(code, "").strip()]
    if missing:
        warnings.warn(f"{where}: block without {'/'.join(missing)} skipped", stacklevel=3)
        return None
    cf = fields.get("CF")
    if cf is not None:
        try:
            parse_ptm_formula(cf)
        except UniprotPtmParseError as exc:
            warnings.warn(f"{where}: {exc}; its dict_composition and proforma_formula are None", stacklevel=3)
    return PtmEntry(
        id=ac,
        name=name,
        feature_type=_feature_type(fields["FT"].strip(), where),
        target=_strip_period(fields["TG"]),
        amino_acid_position=_strip_period(fields["PA"]) if "PA" in fields else None,
        polypeptide_position=_strip_period(fields["PP"]) if "PP" in fields else None,
        correction_formula=cf,
        monoisotopic_mass=_float(fields, "MM", where),
        average_mass=_float(fields, "MA", where),
        cellular_location=_strip_period(fields["LC"]) if "LC" in fields else None,
        taxonomic_ranges=tuple(_parse_tr(v) for v in fields.get("TR", [])),
        keywords=tuple(_strip_period(v) for v in fields.get("KW", [])),
        cross_references=tuple(_parse_dr(v) for v in fields.get("DR", [])),
    )


def parse_ptm_list(path: Path | str) -> PtmDatabase:
    """Parse a ptmlist.txt file into a PtmDatabase.

    Raises UniprotPtmParseError for a malformed value (non-numeric MM/MA, no closing ``//``)
    and UniprotPtmError for a duplicate accession, naming the file line. A block without an
    AC, ID, FT or TG is skipped, and an unknown FT is kept as a plain string; both warn.
    """
    path = Path(path)
    entries: list[PtmEntry] = []
    in_entry = False
    start_line = 0
    current_fields: dict = {}
    seen: dict[str, int] = {}

    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if len(line) < 2:
                continue
            code = line[:2]
            value = line[5:] if len(line) > 5 else ""

            if code == "ID":
                if in_entry:
                    raise UniprotPtmParseError(
                        f"{path.name} line {lineno}: ID before the closing // of line {start_line}"
                    )
                in_entry = True
                start_line = lineno
                current_fields = {"ID": value}
            elif code == "//" and in_entry:
                entry = _build_entry(current_fields, start_line, path)
                if entry is not None:
                    if entry.id in seen:
                        raise UniprotPtmError(
                            f"{path.name} line {start_line}: duplicate accession {entry.id!r} "
                            f"(first at line {seen[entry.id]})"
                        )
                    seen[entry.id] = start_line
                    entries.append(entry)
                in_entry = False
                current_fields = {}
            elif in_entry:
                if code in _MULTI_VALUE:
                    current_fields.setdefault(code, []).append(value)
                elif code.strip():
                    current_fields[code] = value

    if in_entry:
        raise UniprotPtmParseError(f"{path.name} line {start_line}: unterminated entry (no closing //)")
    return PtmDatabase(entries)


def load(source: Path | str | None = None, *, refresh: bool = False) -> PtmDatabase:
    """Load the PTM database: the bundled ptmlist.txt by default, or ``source`` if given.

    ``refresh=True`` downloads the current release from UniProt to the cache
    (``download(force=True)``) and parses that instead; it cannot be combined with ``source``.
    """
    if refresh:
        if source is not None:
            raise ValueError("pass either source or refresh=True, not both")
        return parse_ptm_list(download(force=True))
    if source is not None:
        return parse_ptm_list(source)
    ref = files("uniprotptmpy") / "data" / "ptmlist.txt"
    with as_file(ref) as path:
        return parse_ptm_list(path)
