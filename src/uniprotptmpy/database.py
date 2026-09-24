"""In-memory PTM database with lookup and search."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Iterator
from pathlib import Path

from uniprotptmpy._ptmlist_writer import write_ptmlist
from uniprotptmpy._tabular import write_tsv
from uniprotptmpy.errors import UniprotPtmError
from uniprotptmpy.models import PtmEntry


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
        """Free-text substring search across name, ID, target, and keywords."""
        q = query.lower()
        return [
            entry
            for entry in self._entries
            if q in entry.name.lower()
            or q in entry.id.lower()
            or q in entry.target.lower()
            or any(q in kw.lower() for kw in entry.keywords)
        ]

    def get(self, key: object, default: PtmEntry | None = None) -> PtmEntry | None:
        """Return ``db[key]``, or ``default`` if it would raise. Never raises."""
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key: object) -> PtmEntry:
        """Return the entry by accession (see ``get_by_id``) or, failing that, by name
        (case-insensitive). Raise KeyError for a missing or non-int/str key."""
        entry = None
        if isinstance(key, int | str) and not isinstance(key, bool):
            entry = self.get_by_id(key)
            if entry is None and isinstance(key, str):
                entry = self.get_by_name(key)
        if entry is None:
            raise KeyError(key)
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
