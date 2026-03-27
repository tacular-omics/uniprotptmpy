"""In-memory PTM database with lookup and search."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from uniprotptmpy.models import PtmEntry


class PtmDatabase:
    """Indexed collection of PTM entries with ID, name, and free-text search."""
    def __init__(self, entries: Iterable[PtmEntry]) -> None:
        self._entries: list[PtmEntry] = []
        self._by_id: dict[str, PtmEntry] = {}
        self._by_name_lower: dict[str, PtmEntry] = {}

        for entry in entries:
            self._entries.append(entry)
            self._by_id[entry.id] = entry
            self._by_name_lower[entry.name.lower()] = entry

    def get_by_id(self, ac: str) -> PtmEntry | None:
        """Look up by accession (e.g. 'PTM-0450' or bare '0450')."""
        normalized = ac.upper()
        if not normalized.startswith("PTM-"):
            normalized = f"PTM-{normalized}"
        return self._by_id.get(normalized)

    def get_by_name(self, name: str) -> PtmEntry | None:
        """Case-insensitive exact match on the PTM name."""
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

    def __getitem__(self, key: str) -> PtmEntry:
        entry = self.get_by_id(key) or self.get_by_name(key)
        if entry is None:
            raise KeyError(key)
        return entry

    def __iter__(self) -> Iterator[PtmEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
