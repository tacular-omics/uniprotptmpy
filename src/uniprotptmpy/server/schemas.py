"""Serializers turning PtmEntry dataclasses into JSON-friendly dicts."""

from __future__ import annotations

from typing import Any

from uniprotptmpy.models import CrossReference, PtmEntry, TaxonomicRange


def serialize_xref(xref: CrossReference) -> dict[str, Any]:
    return {"database": xref.database, "accession": xref.accession}


def serialize_taxonomic_range(tr: TaxonomicRange) -> dict[str, Any]:
    return {
        "taxon_name": tr.taxon_name,
        "tax_id": tr.tax_id,
        "description": tr.description,
        "raw": tr.raw,
    }


def serialize_entry(entry: PtmEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "name": entry.name,
        "feature_type": str(entry.feature_type),
        "target": entry.target,
        "amino_acid_position": entry.amino_acid_position,
        "polypeptide_position": entry.polypeptide_position,
        "correction_formula": entry.correction_formula,
        "monoisotopic_mass": entry.monoisotopic_mass,
        "average_mass": entry.average_mass,
        "cellular_location": entry.cellular_location,
        "keywords": list(entry.keywords),
        "proforma_formula": entry.proforma_formula,
        "dict_composition": entry.dict_composition,
        "taxonomic_ranges": [serialize_taxonomic_range(t) for t in entry.taxonomic_ranges],
        "cross_references": [serialize_xref(x) for x in entry.cross_references],
    }
