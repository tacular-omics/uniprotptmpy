#!/usr/bin/env python3
"""Export the bundled UniProt PTM database to JSON for the GitHub Pages browser."""
import json
from pathlib import Path

from uniprotptmpy import load

db = load()

entries = []
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

out = Path("docs/data.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(entries, separators=(",", ":")))
print(f"Exported {len(entries)} entries → {out}")
