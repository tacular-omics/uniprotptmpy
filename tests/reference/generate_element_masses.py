"""Freeze an independent element/isotope mass table for tests/test_reference_masses.py.

Produced with pyteomics 5.0.1 (``pyteomics.mass.nist_mass``, NIST atomic weights and
isotopic compositions) on Python 3.13:

    uv run --with pyteomics==5.0.1 python tests/reference/generate_element_masses.py

pyteomics is not a dependency of uniprotptmpy; only the JSON it writes is committed.
Only the elements that occur in the bundled ptmlist.txt correction formulas (CF lines)
are written. Keys are element symbols ("C").
"""

from __future__ import annotations

import json
import re
from importlib.metadata import version
from pathlib import Path

from pyteomics import mass

import uniprotptmpy

_KEY_RE = re.compile(r"^(\d+)?([A-Z][a-z]?)$")
OUT = Path(__file__).with_name("element_masses.json")


def main() -> None:
    keys: set[str] = set()
    for entry in uniprotptmpy.load():
        for token in entry.dict_composition or {}:
            if _KEY_RE.match(token) is None:
                raise ValueError(f"{entry.id}: unexpected element token {token!r}")
            keys.add(token)

    table: dict[str, dict[str, float]] = {}
    for key in sorted(keys):
        iso, symbol = _KEY_RE.match(key).groups()  # type: ignore[union-attr]
        pyteomics_key = f"{symbol}[{iso}]" if iso else symbol
        table[key] = {
            "mono": mass.calculate_mass(composition={pyteomics_key: 1}),
            "avg": mass.calculate_mass(composition={pyteomics_key: 1}, average=True),
        }

    payload = {
        "source": f"pyteomics {version('pyteomics')} pyteomics.mass.nist_mass",
        "electron_mass": mass.nist_mass["e-"][0][0],
        "elements": table,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(f"wrote {len(table)} elements to {OUT}")


if __name__ == "__main__":
    main()
