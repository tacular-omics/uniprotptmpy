"""In-memory PTM database with lookup and search."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Literal

from uniprotptmpy._ptmlist_writer import write_ptmlist
from uniprotptmpy._tabular import write_tsv
from uniprotptmpy.models import FeatureType, PtmEntry


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

    def find(
        self,
        *,
        text: str | None = None,
        mass_min: float | None = None,
        mass_max: float | None = None,
        mass_type: Literal["mono", "avg"] = "mono",
        residues: Sequence[str] | None = None,
        feature_type: str | None = None,
        keyword: str | None = None,
        taxon_id: int | None = None,
        limit: int | None = None,
    ) -> list[PtmEntry]:
        """Fine-grained AND-combined search across multiple fields.

        All filters are optional; ``None`` values are skipped.  ``residues`` is
        compared case-insensitively against the entry's ``target`` field.
        ``feature_type`` is coerced to :class:`FeatureType` for exact match.
        ``keyword`` is matched case-insensitively against any keyword on the
        entry.  ``taxon_id`` matches if any taxonomic range carries the id.
        """
        text_q = text.lower() if text is not None else None
        residue_set = {r.lower() for r in residues} if residues else None

        ft_value: FeatureType | None = None
        if feature_type is not None:
            try:
                ft_value = FeatureType(feature_type)
            except ValueError:
                return []

        keyword_q = keyword.lower() if keyword is not None else None

        results: list[PtmEntry] = []
        for entry in self._entries:
            if text_q is not None and not (
                text_q in entry.name.lower()
                or text_q in entry.id.lower()
                or text_q in entry.target.lower()
                or any(text_q in kw.lower() for kw in entry.keywords)
            ):
                continue

            if mass_min is not None or mass_max is not None:
                mass = (
                    entry.monoisotopic_mass if mass_type == "mono" else entry.average_mass
                )
                if mass is None:
                    continue
                if mass_min is not None and mass < mass_min:
                    continue
                if mass_max is not None and mass > mass_max:
                    continue

            if residue_set is not None:
                if not entry.target:
                    continue
                if entry.target.lower() not in residue_set:
                    continue

            if ft_value is not None and entry.feature_type != ft_value:
                continue

            if keyword_q is not None and not any(
                keyword_q in kw.lower() for kw in entry.keywords
            ):
                continue

            if taxon_id is not None and not any(
                tr.tax_id == taxon_id for tr in entry.taxonomic_ranges
            ):
                continue

            results.append(entry)
            if limit is not None and len(results) >= limit:
                break

        return results

    def __getitem__(self, key: str) -> PtmEntry:
        entry = self.get_by_id(key) or self.get_by_name(key)
        if entry is None:
            raise KeyError(key)
        return entry

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
