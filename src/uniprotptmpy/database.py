"""In-memory PTM database with lookup and search."""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterable, Iterator
from pathlib import Path

from uniprotptmpy._mass import WHERE_ANY_C, WHERE_ANY_N, WHERE_ANYWHERE, MassIndex, Slot
from uniprotptmpy._ptmlist_writer import write_ptmlist
from uniprotptmpy._tabular import write_tsv
from uniprotptmpy.errors import UniprotPtmError, UniprotPtmKeyError
from uniprotptmpy.models import PtmEntry

# TG residue names -> one-letter codes. "Undefined" (and anything unknown) has none.
_RESIDUE_LETTERS: dict[str, frozenset[str]] = {
    name: frozenset(letters)
    for name, letters in {
        "Alanine": "A",
        "Arginine": "R",
        "Asparagine": "N",
        "Asparagine or Aspartate": "ND",
        "Aspartate": "D",
        "Cysteine": "C",
        "Glutamate": "E",
        "Glutamine": "Q",
        "Glycine": "G",
        "Histidine": "H",
        "Isoleucine": "I",
        "Leucine": "L",
        "Lysine": "K",
        "Methionine": "M",
        "Phenylalanine": "F",
        "Proline": "P",
        "Pyrrolysine": "O",
        "Selenocysteine": "U",
        "Serine": "S",
        "Threonine": "T",
        "Tryptophan": "W",
        "Tyrosine": "Y",
        "Valine": "V",
    }.items()
}
_PP_WHERE = {
    "N-terminal": WHERE_ANY_N,
    "C-terminal": WHERE_ANY_C,
    "Anywhere": WHERE_ANYWHERE,
    "Protein core": WHERE_ANYWHERE,
}
_PP_TOKEN = re.compile(r"N-terminal|C-terminal|Anywhere|Protein core")


def _slots(entry: PtmEntry) -> tuple[Slot, ...]:
    """Where ``entry`` may sit, for search_mass: one slot per TG residue, with its PP position.

    A crosslink ("Cysteine-Serine", PP "Anywhere-C-terminal") gives one slot per residue.
    Without a usable PP every residue may sit anywhere.
    """
    residues = entry.target.split("-")
    positions = _PP_TOKEN.findall(entry.polypeptide_position or "")
    if len(positions) != len(residues):
        positions = ["Anywhere"] * len(residues)
    return tuple(
        (_RESIDUE_LETTERS.get(name, frozenset()), _PP_WHERE[pp]) for name, pp in zip(residues, positions, strict=True)
    )


# Joins the lowercased search fields of one entry. A query without this character can
# only match inside one field, so one substring test replaces one test per field.
_SEP = "\x00"


def _fields(entry: PtmEntry) -> list[str]:
    """Return the lowercased name, id, target and keywords of ``entry``: the fields search() looks in."""
    return [entry.name.lower(), entry.id.lower(), entry.target.lower(), *(k.lower() for k in entry.keywords)]


def _haystack(entry: PtmEntry) -> str:
    """Return ``_fields(entry)`` joined by ``_SEP``."""
    return _SEP.join(_fields(entry))


class PtmDatabase:
    """Indexed collection of PTM entries with ID, name, and free-text search."""

    def __init__(self, entries: Iterable[PtmEntry]) -> None:
        """Index ``entries``. Raises UniprotPtmError on a duplicate accession; on a duplicate
        name (case-insensitive) the first entry keeps the name."""
        self._entries: list[PtmEntry] = []
        self._by_id: dict[str, PtmEntry] = {}
        self._by_name_lower: dict[str, PtmEntry] = {}

        for entry in entries:
            if entry.id in self._by_id:
                raise UniprotPtmError(f"duplicate accession {entry.id!r} ({entry.name!r})")
            self._entries.append(entry)
            self._by_id[entry.id] = entry
            self._by_name_lower.setdefault(entry.name.lower(), entry)

        self._mass_index: MassIndex[PtmEntry] | None = None
        # residue letter -> entries whose TG includes it, in file order.
        self._by_site: dict[str, list[PtmEntry]] = {}
        for e in self._entries:
            for letter in sorted(frozenset().union(*(sites for sites, _ in _slots(e)))):
                self._by_site.setdefault(letter, []).append(e)

        # (entry, lowercased name/id/target/keywords joined by _SEP), in file order, for search().
        self._haystacks: list[tuple[PtmEntry, str]] = [(e, _haystack(e)) for e in self._entries]

    def get_by_id(self, id: int | str | None = None, *, ac: int | str | None = None) -> PtmEntry | None:
        """Look up by accession: 'PTM-0450', bare '0450', unpadded '450' or 'PTM-450', or 450.

        The prefix is case-insensitive and surrounding whitespace is ignored. Returns
        None for an unknown accession or a key that is not an int or str (``bool`` included).
        The keyword ``ac=`` is a deprecated alias for ``id=``.
        """
        if ac is not None:
            warnings.warn("get_by_id(ac=...) is deprecated; use get_by_id(id=...)", DeprecationWarning, stacklevel=2)
            if id is None:
                id = ac
        if isinstance(id, bool):
            return None
        if isinstance(id, int):
            return self._by_id.get(f"PTM-{id:04d}") if id >= 0 else None
        if not isinstance(id, str):
            return None
        normalized = id.strip().upper()
        if not normalized.startswith("PTM-"):
            normalized = f"PTM-{normalized}"
        entry = self._by_id.get(normalized)
        digits = normalized.removeprefix("PTM-")
        if entry is None and digits.isascii() and digits.isdigit():
            entry = self._by_id.get(f"PTM-{int(digits):04d}")
        return entry

    def get_by_name(self, name: str) -> PtmEntry | None:
        """Case-insensitive exact match on the PTM name; None on a miss.

        If two entries share a name (ignoring case), the first one in file order is returned.
        """
        if not isinstance(name, str):
            return None
        return self._by_name_lower.get(name.lower())

    def search(self, query: str) -> list[PtmEntry]:
        """Free-text substring search across name, ID, target, and keywords; [] for a non-str query."""
        if not isinstance(query, str):
            return []
        q = query.lower()
        if _SEP in q:
            # Rare: the query could span two joined fields, so test each field.
            return [e for e in self._entries if any(q in f for f in _fields(e))]
        return [entry for entry, haystack in self._haystacks if q in haystack]

    def search_mass(
        self,
        delta: float,
        *,
        tolerance: float = 0.01,
        unit: str = "da",
        site: str | None = None,
        position: str | None = None,
    ) -> list[tuple[PtmEntry, float]]:
        """Return ``(entry, error)`` pairs whose delta mass is within ``tolerance`` of ``delta``.

        The mass is the monoisotopic delta mass, ``monoisotopic_mass`` (MM).
        ``error`` is ``delta - mass`` in Da (positive when ``delta`` is heavier). Pairs are
        sorted by ``abs(error)``, ties in mass order then database order. Entries without
        ``monoisotopic_mass`` are skipped. The mass index is sorted once, on the first call, and
        searched with bisect.

        Args:
            delta: Observed monoisotopic mass shift in Da; may be negative.
            tolerance: Window half-width in Da; both edges are inclusive (with a 1e-9 relative
                slack for float rounding), and ``0`` means an exact match.
            unit: Only ``"da"`` (the default), exact and lowercase; anything else raises.
                ppm is not offered: a ppm window on a delta mass is ill-defined (relative
                to the delta, or to the modified peptide's mass?). The keyword is kept so
                the call matches ``tacular.tolerance``; other units may be added later.
            site: Residue letter(s) the modification sits on, e.g. ``"S"`` or ``"STY"``
                (any of them), or ``"N-term"`` / ``"C-term"`` for a terminus modification.
                Several letters mean any of them (``get_by_site`` takes exactly one residue).
                Matched against the residues of ``target`` (each residue of a crosslink;
                "Asparagine or Aspartate" is N and D). UniProt has no terminus-only entries,
                so ``"N-term"`` finds none.
            position: Where the modified residue was observed: ``"anywhere"`` (inside the
                sequence), ``"peptide n-term"``, ``"peptide c-term"``, ``"protein n-term"``
                or ``"protein c-term"`` (case-insensitive). Keeps entries allowed there;
                a modification allowed anywhere is allowed at a terminus too. Matched against
                ``polypeptide_position`` of the same residue; UniProt does not say protein or
                peptide, so an N-terminal entry matches both N-terminal positions.

        Raises:
            UniprotPtmError: ``delta`` or ``tolerance`` is not a finite number (or ``tolerance`` < 0),
                or ``unit``, ``site`` or ``position`` is not one of the values above.
        """
        if self._mass_index is None:
            self._mass_index = MassIndex((e, e.monoisotopic_mass, _slots(e)) for e in self._entries)
        return self._mass_index.search(
            delta, tolerance=tolerance, unit=unit, site=site, position=position, error=UniprotPtmError
        )

    def get_by_site(self, site: str) -> list[PtmEntry]:
        """Return entries whose target includes residue ``site`` (one letter, case-insensitive), in file order.

        Like psimodpy's ``get_by_origin``; crosslinks appear under each of their residues.
        An unknown site or a non-string returns ``[]``.
        Takes exactly one residue; ``search_mass(site=...)`` takes several letters (any of them).
        """
        if not isinstance(site, str):
            return []
        return list(self._by_site.get(site.strip().upper(), []))

    def get(self, key: object, default: PtmEntry | None = None) -> PtmEntry | None:
        """Return ``db[key]``, or ``default`` if it would raise. Never raises."""
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key: object) -> PtmEntry:
        """Return the entry by accession (see ``get_by_id``) or, failing that, by name
        (case-insensitive). Raise UniprotPtmKeyError (a KeyError) for a missing or non-int/str key."""
        entry = None
        if isinstance(key, int | str) and not isinstance(key, bool):
            entry = self.get_by_id(key)
            if entry is None and isinstance(key, str):
                entry = self.get_by_name(key)
        if entry is None:
            raise UniprotPtmKeyError(key)
        return entry

    def __contains__(self, key: object) -> bool:
        """True if ``db[key]`` would succeed; also accepts a ``PtmEntry`` from this database."""
        if isinstance(key, PtmEntry):
            return self._by_id.get(key.id) == key
        return self.get(key) is not None

    def __iter__(self) -> Iterator[PtmEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def write_tsv(self, path: Path | str, *, delimiter: str = "\t") -> Path:
        """Serialize all entries to a tab-separated file. Pass ``delimiter=','`` for CSV."""
        return write_tsv(self._entries, path, delimiter=delimiter)

    def write_ptmlist(self, path: Path | str) -> Path:
        """Serialize all entries to ptmlist.txt format."""
        return write_ptmlist(self._entries, path)
