"""Links from UniProt PTM entries to PSI-MOD and Unimod (the ``link`` extra).

``psimod_ids``/``unimod_ids`` only parse ``cross_references`` and need nothing extra.
Resolving an id to an entry needs psimodpy / unimodpy, installed by
``pip install "uniprotptmpy[link]"``. Each linked database is loaded (bundled data) once
per process, on first use.
"""

from __future__ import annotations

import functools
import re
from typing import TYPE_CHECKING, Any, Literal

from uniprotptmpy.errors import UniprotPtmError

if TYPE_CHECKING:
    from uniprotptmpy.models import CrossReference

type LinkTarget = Literal["psimod", "unimod"]

LINK_TARGETS: tuple[LinkTarget, ...] = ("psimod", "unimod")
INSTALL_HINT = 'pip install "uniprotptmpy[link]"'

_MASS_FIELDS = {"psimod": ("diff_mono", "diff_avg"), "unimod": ("delta_mono_mass", "delta_avge_mass")}
_DIGITS = re.compile(r"(?:MOD:|UNIMOD:)?0*(\d+)", re.IGNORECASE)


def _ids(refs: tuple[CrossReference, ...], database: str, prefix: str, width: int) -> tuple[str, ...]:
    out: dict[str, None] = {}
    for ref in refs:
        if ref.database != database:
            continue
        match = _DIGITS.fullmatch(ref.accession.strip())
        if match is not None:
            out[f"{prefix}{int(match.group(1)):0{width}d}"] = None
    return tuple(out)


def psimod_ids(refs: tuple[CrossReference, ...]) -> tuple[str, ...]:
    """PSI-MOD accessions as ``"MOD:00046"`` (five digits), in file order, without duplicates."""
    return _ids(refs, "PSI-MOD", "MOD:", 5)


def unimod_ids(refs: tuple[CrossReference, ...]) -> tuple[str, ...]:
    """Unimod accessions as ``"UNIMOD:21"``, in file order, without duplicates."""
    return _ids(refs, "Unimod", "UNIMOD:", 1)


@functools.cache
def _database(target: LinkTarget) -> Any:
    """The linked package's bundled database; raises ImportError without the extra."""
    if target == "psimod":
        import psimodpy

        return psimodpy.load()
    import unimodpy

    return unimodpy.load()


def check_target(target: object) -> LinkTarget:
    if target == "psimod":
        return "psimod"
    if target == "unimod":
        return "unimod"
    raise UniprotPtmError(f"unknown link target {target!r}: use 'psimod' or 'unimod'")


def linked_database(target: LinkTarget) -> Any:
    """The linked database, or UniprotPtmError naming the extra when it is not installed."""
    try:
        return _database(target)
    except ImportError as exc:
        package = "psimodpy" if target == "psimod" else "unimodpy"
        raise UniprotPtmError(
            f"resolve({target!r}) needs {package}, which is not installed; install the link extra: {INSTALL_HINT}"
        ) from exc


def resolve(ids: tuple[str, ...], target: LinkTarget) -> tuple[Any, ...]:
    """Entries for ``ids`` in the ``target`` database; ids it does not know are skipped."""
    db = linked_database(target)
    found = (db.get_by_id(i) for i in ids)
    return tuple(e for e in found if e is not None)


def fallback_mass(psimod: tuple[str, ...], unimod: tuple[str, ...], *, monoisotopic: bool) -> float | None:
    """First mass among the linked PSI-MOD entries, then the linked Unimod entries.

    A database whose package is not installed is skipped silently; None if nothing has a mass.
    """
    links: tuple[tuple[tuple[str, ...], LinkTarget], ...] = ((psimod, "psimod"), (unimod, "unimod"))
    for ids, target in links:
        if not ids:
            continue
        try:
            db = _database(target)
        except ImportError:
            continue
        # Read the fields directly (not get_mass()) so psimodpy/unimodpy 1.0 work too.
        field = _MASS_FIELDS[target][0 if monoisotopic else 1]
        for i in ids:
            entry = db.get_by_id(i)
            mass = getattr(entry, field) if entry is not None else None
            if mass is not None:
                return mass
    return None
