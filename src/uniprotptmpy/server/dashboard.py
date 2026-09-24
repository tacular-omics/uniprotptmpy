"""Build the data payload consumed by the static dashboard."""

from __future__ import annotations

from typing import TypedDict

from uniprotptmpy import PtmDatabase, load


class DashboardXref(TypedDict):
    database: str
    accession: str


class DashboardTaxon(TypedDict):
    taxon_name: str
    description: str


class DashboardRow(TypedDict):
    """One entry in the dashboard payload (``/data.json``, ``docs/data.json``)."""

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
    cross_references: list[DashboardXref]
    taxonomic_ranges: list[DashboardTaxon]


def dashboard_entries(db: PtmDatabase | None = None) -> list[DashboardRow]:
    """Return the dashboard payload for ``db`` (the bundled database if omitted)."""
    if db is None:
        db = load()
    entries: list[DashboardRow] = []
    for entry in db:
        entries.append(
            {
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
                    {"database": xr.database, "accession": xr.accession} for xr in entry.cross_references
                ],
                "taxonomic_ranges": [
                    {"taxon_name": tr.taxon_name, "description": tr.description} for tr in entry.taxonomic_ranges
                ],
            }
        )
    return entries
