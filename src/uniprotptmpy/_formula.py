"""Chemical formula parsing and ProForma notation conversion."""

from __future__ import annotations

import re

from uniprotptmpy.errors import UniprotPtmParseError

# One CF token: element or isotope, then a signed count. Isotopes may be written
# "13C6", "[13C]6" or "[13C6]"; the dict key is "13C".
_CF_TOKEN_RE = re.compile(
    r"(?:\[(?P<bmass>\d+)(?P<belem>[A-Z][a-z]?)(?P<bcount>-?\d+)?\](?P<acount>-?\d+)?"
    r"|(?P<mass>\d+)?(?P<elem>[A-Z][a-z]?)(?P<count>-?\d+))"
)
_KEY_RE = re.compile(r"(\d*)([A-Z][a-z]?)")


def parse_ptm_formula(cf: str) -> dict[str, int]:
    """Parse a ptmlist CF string like 'H-3 N-1 O1' into {element: count}; isotope keys are like '13C'.

    Zero totals are dropped. Raises UniprotPtmParseError for a token it cannot read.
    """
    counts: dict[str, int] = {}
    for token in cf.split():
        m = _CF_TOKEN_RE.fullmatch(token)
        if m is None:
            raise UniprotPtmParseError(f"cannot parse CF token {token!r} in {cf!r}")
        if m["belem"] is not None:
            if m["bcount"] is not None and m["acount"] is not None:
                raise UniprotPtmParseError(f"cannot parse CF token {token!r} in {cf!r}")
            key = f"{m['bmass']}{m['belem']}"
            count = int(m["bcount"] or m["acount"] or 1)
        else:
            key = f"{m['mass'] or ''}{m['elem']}"
            count = int(m["count"])
        counts[key] = counts.get(key, 0) + count
    return {k: v for k, v in counts.items() if v != 0}


def _hill_sort_key(key: str) -> tuple[int, str, int]:
    m = _KEY_RE.fullmatch(key)
    mass, element = (int(m[1]) if m[1] else 0, m[2]) if m else (0, key)
    order = {"C": 0, "H": 1}
    return (order.get(element, 2), element, mass)


def to_proforma_formula(composition: dict[str, int]) -> str:
    """Convert a composition dict to a ProForma Hill-notation string: 'C2H3NO', 'H-3N-1', '[13C6]H-1'.

    No spaces; a count of 1 is omitted; zero counts are dropped; isotopes are bracketed.
    """
    parts = []
    for key in sorted(composition, key=_hill_sort_key):
        count = composition[key]
        if count == 0:
            continue
        suffix = "" if count == 1 else str(count)
        parts.append(f"[{key}{suffix}]" if key[0].isdigit() else f"{key}{suffix}")
    return "".join(parts)
