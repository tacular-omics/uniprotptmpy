"""Data models for PTM entries and related types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from uniprotptmpy import _links
from uniprotptmpy._formula import parse_ptm_formula, to_proforma_formula
from uniprotptmpy.errors import UniprotPtmParseError


class FeatureType(StrEnum):
    """UniProt feature key for the PTM."""

    CROSSLNK = "CROSSLNK"
    MOD_RES = "MOD_RES"
    LIPID = "LIPID"
    CARBOHYD = "CARBOHYD"
    DISULFID = "DISULFID"


@dataclass(frozen=True, slots=True)
class CrossReference:
    """Cross-reference to an external database (RESID, PSI-MOD, etc.)."""

    database: str
    accession: str


@dataclass(frozen=True, slots=True)
class TaxonomicRange:
    """Taxonomic scope of a PTM."""

    taxon_name: str
    tax_id: int | None
    description: str
    raw: str


@dataclass(frozen=True, slots=True)
class PtmEntry:
    """A single post-translational modification entry from the UniProt controlled vocabulary."""

    id: str  # AC field e.g. "PTM-0450"
    name: str  # ID field (human-readable name)
    feature_type: FeatureType | str  # FT; the raw string for a key newer than FeatureType
    target: str  # TG (period stripped)
    amino_acid_position: str | None  # PA (period stripped)
    polypeptide_position: str | None  # PP (period stripped)
    correction_formula: str | None  # CF raw string e.g. "H-3 N-1"
    monoisotopic_mass: float | None  # MM
    average_mass: float | None  # MA
    cellular_location: str | None  # LC (period stripped)
    taxonomic_ranges: tuple[TaxonomicRange, ...]
    keywords: tuple[str, ...]  # KW (period stripped)
    cross_references: tuple[CrossReference, ...]

    @property
    def accession(self) -> str:
        """The accession, e.g. "PTM-0450"; same as ``id``. psimodpy and unimodpy entries have ``accession`` too."""
        return self.id

    @property
    def psimod_ids(self) -> tuple[str, ...]:
        """Linked PSI-MOD accessions from ``cross_references``, normalized to ``"MOD:00046"`` form."""
        return _links.psimod_ids(self.cross_references)

    @property
    def unimod_ids(self) -> tuple[str, ...]:
        """Linked Unimod accessions from ``cross_references``, normalized to ``"UNIMOD:21"`` form."""
        return _links.unimod_ids(self.cross_references)

    def resolve(self, target: _links.LinkTarget) -> tuple[Any, ...]:
        """The linked entries in PSI-MOD (``"psimod"``) or Unimod (``"unimod"``).

        Returns ``psimodpy.PsiModEntry`` or ``unimodpy.UnimodEntry`` objects for
        ``psimod_ids``/``unimod_ids``, from each package's bundled data (loaded once per
        process); an id the linked release does not know is skipped. Needs the ``link``
        extra (``pip install "uniprotptmpy[link]"``); without it, or for another
        ``target``, raises ``UniprotPtmError``.
        """
        target = _links.check_target(target)
        ids = self.psimod_ids if target == "psimod" else self.unimod_ids
        return _links.resolve(ids, target)

    def get_mass(self, *, monoisotopic: bool = True) -> float | None:
        """The mass difference in Da: monoisotopic (default) or, with ``monoisotopic=False``, average.

        Fallback order: UniProt's own ``monoisotopic_mass``/``average_mass``; if that is
        ``None`` and the ``link`` extra is installed, the first linked PSI-MOD entry with
        that mass, then the first linked Unimod entry; else ``None``. Without the extra
        this is exactly the UniProt field.
        """
        mass = self.monoisotopic_mass if monoisotopic else self.average_mass
        if mass is not None:
            return mass
        psimod, unimod = self.psimod_ids, self.unimod_ids
        if not psimod and not unimod:
            return None
        return _links.fallback_mass(psimod, unimod, monoisotopic=monoisotopic)

    @property
    def dict_composition(self) -> dict[str, int] | None:
        """Correction formula as {element: count} (isotopes keyed like "13C").

        None if there is no formula or it cannot be parsed (load() warns about such entries).
        """
        if self.correction_formula is None:
            return None
        try:
            return parse_ptm_formula(self.correction_formula)
        except UniprotPtmParseError:
            return None

    @property
    def proforma_formula(self) -> str | None:
        """Correction formula as a ProForma Hill-notation string ("HO3P"); None when dict_composition is None."""
        comp = self.dict_composition
        if comp is None:
            return None
        return to_proforma_formula(comp)
