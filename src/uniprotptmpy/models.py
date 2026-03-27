from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from uniprotptmpy._formula import parse_ptm_formula, to_proforma_formula


class FeatureType(StrEnum):
    CROSSLNK = "CROSSLNK"
    MOD_RES = "MOD_RES"
    LIPID = "LIPID"
    CARBOHYD = "CARBOHYD"
    DISULFID = "DISULFID"


@dataclass(frozen=True, slots=True)
class CrossReference:
    database: str
    accession: str


@dataclass(frozen=True, slots=True)
class TaxonomicRange:
    taxon_name: str
    tax_id: int | None
    description: str
    raw: str


@dataclass(frozen=True, slots=True)
class PtmEntry:
    id: str  # AC field e.g. "PTM-0450"
    name: str  # ID field (human-readable name)
    feature_type: FeatureType  # FT
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
    def dict_composition(self) -> dict[str, int] | None:
        if self.correction_formula is None:
            return None
        return parse_ptm_formula(self.correction_formula)

    @property
    def proforma_formula(self) -> str | None:
        comp = self.dict_composition
        if comp is None:
            return None
        return to_proforma_formula(comp)
