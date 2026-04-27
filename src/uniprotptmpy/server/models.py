"""Pydantic response models for the uniprotptmpy REST + MCP server.

These models are the single source of truth for the wire shape returned by
both transports.  Keeping the models here (rather than inline in ``app.py``)
lets tests import them and lets FastMCP derive ``outputSchema`` automatically.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from uniprotptmpy.models import CrossReference as _CrossReference
from uniprotptmpy.models import PtmEntry as _PtmEntry
from uniprotptmpy.models import TaxonomicRange as _TaxonomicRange


class CrossReference(BaseModel):
    database: str
    accession: str


class TaxonomicRange(BaseModel):
    taxon_name: str
    tax_id: int | None
    description: str
    raw: str


class PtmEntry(BaseModel):
    """Full UniProt PTM entry."""

    id: str
    name: str
    feature_type: str
    target: str
    amino_acid_position: str | None
    polypeptide_position: str | None
    correction_formula: str | None
    proforma_formula: str | None
    monoisotopic_mass: float | None
    average_mass: float | None
    cellular_location: str | None
    keywords: list[str]
    dict_composition: dict[str, int] | None
    taxonomic_ranges: list[TaxonomicRange]
    cross_references: list[CrossReference]


class PtmSummary(BaseModel):
    """Compact entry shape returned by ``search`` and similar list endpoints."""

    id: str
    name: str
    feature_type: str
    target: str
    monoisotopic_mass: float | None


class EntryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[PtmEntry]


class SearchResponse(BaseModel):
    query: str
    total: int
    limit: int
    items: list[PtmSummary] = Field(
        description="Lightweight summaries; call get_by_id for the full record.",
    )


# ---------------------------------------------------------------------------
# Converters from domain dataclasses to Pydantic models
# ---------------------------------------------------------------------------


def _xref(x: _CrossReference) -> CrossReference:
    return CrossReference(database=x.database, accession=x.accession)


def _taxonomic_range(t: _TaxonomicRange) -> TaxonomicRange:
    return TaxonomicRange(
        taxon_name=t.taxon_name,
        tax_id=t.tax_id,
        description=t.description,
        raw=t.raw,
    )


def to_ptm_entry(entry: _PtmEntry) -> PtmEntry:
    return PtmEntry(
        id=entry.id,
        name=entry.name,
        feature_type=str(entry.feature_type),
        target=entry.target,
        amino_acid_position=entry.amino_acid_position,
        polypeptide_position=entry.polypeptide_position,
        correction_formula=entry.correction_formula,
        proforma_formula=entry.proforma_formula,
        monoisotopic_mass=entry.monoisotopic_mass,
        average_mass=entry.average_mass,
        cellular_location=entry.cellular_location,
        keywords=list(entry.keywords),
        dict_composition=entry.dict_composition,
        taxonomic_ranges=[_taxonomic_range(t) for t in entry.taxonomic_ranges],
        cross_references=[_xref(x) for x in entry.cross_references],
    )


def to_ptm_summary(entry: _PtmEntry) -> PtmSummary:
    return PtmSummary(
        id=entry.id,
        name=entry.name,
        feature_type=str(entry.feature_type),
        target=entry.target,
        monoisotopic_mass=entry.monoisotopic_mass,
    )
