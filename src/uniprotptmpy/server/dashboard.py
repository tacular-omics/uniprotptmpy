"""Build the data payload consumed by the static dashboard."""

from __future__ import annotations

from uniprotptmpy import load


def dashboard_entries() -> list[dict]:
    db = load()
    entries: list[dict] = []
    for entry in db:
        entries.append({
            "id": entry.id,
            "name": entry.name,
            "feature_type": str(entry.feature_type),
            "target": entry.target,
            "amino_acid_position": entry.amino_acid_position,
            "polypeptide_position": entry.polypeptide_position,
            "correction_formula": entry.correction_formula,
            "proforma_formula": entry.proforma_formula,
            "monoisotopic_mass": entry.monoisotopic_mass,
            "average_mass": entry.average_mass,
            "cellular_location": entry.cellular_location,
            "keywords": list(entry.keywords),
            "cross_references": [
                {"database": xr.database, "accession": xr.accession}
                for xr in entry.cross_references
            ],
            "taxonomic_ranges": [
                {"taxon_name": tr.taxon_name, "description": tr.description}
                for tr in entry.taxonomic_ranges
            ],
        })
    return entries
