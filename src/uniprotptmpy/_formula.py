"""Chemical formula parsing and ProForma notation conversion."""

from __future__ import annotations

import re

_CF_TOKEN_RE = re.compile(r"([A-Z][a-z]?)(-?\d+)")


def parse_ptm_formula(cf: str) -> dict[str, int]:
    """Parse a ptmlist CF string like 'H-3 N-1 O1' into {element: count}."""
    counts: dict[str, int] = {}
    for m in _CF_TOKEN_RE.finditer(cf):
        elem, count = m.group(1), int(m.group(2))
        counts[elem] = counts.get(elem, 0) + count
    return {k: v for k, v in counts.items() if v != 0}


def _hill_sort_key(element: str) -> tuple[int, str]:
    order = {"C": 0, "H": 1}
    return (order.get(element, 2), element)


def to_proforma_formula(composition: dict[str, int]) -> str:
    """Convert element composition dict to ProForma Hill-notation string."""
    parts = []
    for elem in sorted(composition, key=_hill_sort_key):
        count = composition[elem]
        if count == 1:
            parts.append(elem)
        else:
            parts.append(f"{elem}{count}")
    return " ".join(parts)
