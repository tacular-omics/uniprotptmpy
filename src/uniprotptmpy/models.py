"""Data models for PTM entries and related types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from uniprotptmpy._formula import parse_ptm_formula, to_proforma_formula


class FeatureType(StrEnum):
    """UniProt feature key for the PTM."""

    CROSSLNK = "CROSSLNK"
    MOD_RES = "MOD_RES"
    LIPID = "LIPID"
    CARBOHYD = "CARBOHYD"
    DISULFID = "DISULFID"


@dataclass(frozen=True, slots=True)
class CrossReference:
    """Cross-reference to an external database (RESID, PSI-MOD, etc.)."""

    database: str
    accession: str


@dataclass(frozen=True, slots=True)
class TaxonomicRange:
    """Taxonomic scope of a PTM."""

    taxon_name: str
    tax_id: int | None
    description: str
    raw: str


@dataclass(frozen=True, slots=True)
class PtmEntry:
    """A single post-translational modification entry from the UniProt controlled vocabulary."""

    id: str  # AC field e.g. "PTM-0450"
    name: str  # ID field (human-readable name)
    feature_type: FeatureType | str  # FT; the raw string for a key newer than FeatureType
    target: str  # TG (period stripped)
    amino_acid_position: str | None  # PA (period stripped)
    polypeptide_position: str | None  # PP (period stripped)
    correction_formula: str | None  # CF raw string e.g. "H-3 N-1"
    monoisotopic_mass: float | None  # MM
    average_mass: float | None  # MA
    cellular_location: str | None  # LC (period stripped)
    taxonomic_ranges: tuple[TaxonomicRange, ...]
    keywords: tuple[str, ...]  # KW (period stripped)
    cross_references: tuple[CrossReference, ...]

    @property
    def accession(self) -> str:
        """The accession, e.g. "PTM-0450"; same as ``id`` (named as in psimodpy and unimodpy)."""
        return self.id

    @property
    def dict_composition(self) -> dict[str, int] | None:
        """Correction formula as {element: count} (isotopes keyed like "13C"), or None if no formula.

        Raises UniprotPtmParseError if the CF cannot be parsed (load() warns about such entries).
        """
        if self.correction_formula is None:
            return None
        return parse_ptm_formula(self.correction_formula)

    @property
    def proforma_formula(self) -> str | None:
        """Correction formula as a ProForma Hill-notation string without spaces ("HO3P"), or None."""
        comp = self.dict_composition
        if comp is None:
            return None
        return to_proforma_formula(comp)
