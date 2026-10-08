"""psimod_ids / unimod_ids / resolve() / get_mass() and the ``link`` extra (1.1)."""

from __future__ import annotations

import dataclasses
import inspect
import sys

import pytest

from uniprotptmpy import PtmDatabase, UniprotPtmError, _links, load
from uniprotptmpy.models import CrossReference, PtmEntry

psimodpy = pytest.importorskip("psimodpy")
unimodpy = pytest.importorskip("unimodpy")


@pytest.fixture
def no_extra(monkeypatch: pytest.MonkeyPatch):
    """Simulate an install without the ``link`` extra: importing psimodpy/unimodpy fails."""
    _links._database.cache_clear()
    monkeypatch.setitem(sys.modules, "psimodpy", None)
    monkeypatch.setitem(sys.modules, "unimodpy", None)
    yield
    _links._database.cache_clear()


def _entry(db: PtmDatabase, **changes) -> PtmEntry:
    return dataclasses.replace(db["PTM-0253"], **changes)


# ---------------------------------------------------------------- ids (no extra needed)


def test_id_counts(db: PtmDatabase) -> None:
    assert sum(bool(e.psimod_ids) for e in db) == 512
    assert sum(bool(e.unimod_ids) for e in db) == 252


def test_ids_are_normalized(db: PtmDatabase) -> None:
    for e in db:
        assert all(i.startswith("MOD:") and len(i) == 9 and i[4:].isdigit() for i in e.psimod_ids)
        assert all(i.startswith("UNIMOD:") and i[7:].isdigit() and not i[7:].startswith("0") for i in e.unimod_ids)
    phospho = db.get_by_name("Phosphoserine")
    assert phospho is not None
    assert phospho.psimod_ids == ("MOD:00046",)
    assert phospho.unimod_ids == ("UNIMOD:21",)


def test_ids_parse_variants_and_dedupe(db: PtmDatabase) -> None:
    refs = (
        CrossReference("Unimod", "021"),
        CrossReference("Unimod", "UNIMOD:21"),
        CrossReference("PSI-MOD", "mod:46"),
        CrossReference("PSI-MOD", "MOD:00047"),
        CrossReference("PSI-MOD", "junk"),
        CrossReference("RESID", "AA0037"),
    )
    e = _entry(db, cross_references=refs)
    assert e.unimod_ids == ("UNIMOD:21",)
    assert e.psimod_ids == ("MOD:00046", "MOD:00047")


@pytest.mark.parametrize(
    ("database", "accession"),
    [("PSI-MOD", "UNIMOD:46"), ("PSI-MOD", "unimod:00046"), ("Unimod", "MOD:00021"), ("Unimod", "mod:21")],
)
def test_ids_reject_the_other_databases_prefix(db: PtmDatabase, database: str, accession: str) -> None:
    e = _entry(db, cross_references=(CrossReference(database, accession),))
    assert e.psimod_ids == ()
    assert e.unimod_ids == ()


def test_ids_accept_own_prefix_or_bare_digits(db: PtmDatabase) -> None:
    refs = (CrossReference("PSI-MOD", "46"), CrossReference("Unimod", "unimod:21"))
    e = _entry(db, cross_references=refs)
    assert e.psimod_ids == ("MOD:00046",)
    assert e.unimod_ids == ("UNIMOD:21",)


def test_ids_work_without_extra(db: PtmDatabase, no_extra: None) -> None:
    assert db.get_by_name("Phosphoserine").psimod_ids == ("MOD:00046",)  # type: ignore[union-attr]


# ---------------------------------------------------------------- resolve()


def test_resolve(db: PtmDatabase) -> None:
    phospho = db.get_by_name("Phosphoserine")
    assert phospho is not None
    (mod,) = phospho.resolve("psimod")
    assert isinstance(mod, psimodpy.PsiModEntry)
    assert mod.name == "O-phospho-L-serine"
    (uni,) = phospho.resolve("unimod")
    assert isinstance(uni, unimodpy.UnimodEntry)
    assert uni.name == "Phospho"


def test_resolve_every_link(db: PtmDatabase) -> None:
    for e in db:
        assert [m.accession for m in e.resolve("psimod")] == list(e.psimod_ids)
        assert [m.accession for m in e.resolve("unimod")] == list(e.unimod_ids)


def test_resolve_skips_unknown_ids(db: PtmDatabase) -> None:
    e = _entry(db, cross_references=(CrossReference("PSI-MOD", "MOD:99999"), CrossReference("PSI-MOD", "MOD:00046")))
    assert [m.accession for m in e.resolve("psimod")] == ["MOD:00046"]
    assert _entry(db, cross_references=()).resolve("unimod") == ()


@pytest.mark.parametrize("target", ["PSI-MOD", "resid", "", None, 1])
def test_resolve_bad_target(db: PtmDatabase, target: object) -> None:
    with pytest.raises(UniprotPtmError, match="link target"):
        db["PTM-0253"].resolve(target)  # type: ignore[arg-type]


@pytest.mark.parametrize("target", ["psimod", "unimod"])
def test_resolve_without_extra_says_how_to_install(db: PtmDatabase, no_extra: None, target: str) -> None:
    with pytest.raises(UniprotPtmError, match=r"uniprotptmpy\[link\]") as info:
        db["PTM-0253"].resolve(target)  # type: ignore[arg-type]
    assert isinstance(info.value.__cause__, ImportError)


def test_link_extra_is_declared() -> None:
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    # Capped major pins, per the tacular-omics sibling pin policy.
    assert pyproject["project"]["optional-dependencies"]["link"] == ["psimodpy>=1.1,<2", "unimodpy>=1.1,<2"]


# ---------------------------------------------------------------- get_mass()


def test_get_mass_signature(db: PtmDatabase) -> None:
    params = inspect.signature(db["PTM-0253"].get_mass).parameters
    assert params["monoisotopic"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["monoisotopic"].default is True


def test_get_mass_prefers_uniprot(db: PtmDatabase) -> None:
    for e in db:
        if e.monoisotopic_mass is not None:
            assert e.get_mass() == e.monoisotopic_mass
        if e.average_mass is not None:
            assert e.get_mass(monoisotopic=False) == e.average_mass


def test_get_mass_is_only_the_uniprot_field(db: PtmDatabase) -> None:
    # With the link extra installed, get_mass() still never fills a missing mass from a link.
    missing = [e for e in db if e.monoisotopic_mass is None and (e.psimod_ids or e.unimod_ids)]
    assert missing
    for e in db:
        assert e.get_mass() == e.monoisotopic_mass
        assert e.get_mass(monoisotopic=False) == e.average_mass


def test_get_mass_does_not_use_links_ptm_0133(db: PtmDatabase) -> None:
    # Glycine radical: UniProt gives no mass; the linked PSI-MOD term says 0.0.
    e = db["PTM-0133"]
    assert e.get_mass() is None
    assert [m.diff_mono for m in e.resolve("psimod")] == [0.0]


def test_get_mass_without_extra_is_the_uniprot_field(db: PtmDatabase, no_extra: None) -> None:
    for e in db:
        assert e.get_mass() == e.monoisotopic_mass
        assert e.get_mass(monoisotopic=False) == e.average_mass


def test_search_mass_is_the_same_with_and_without_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    def everything() -> list[tuple[str, float]]:
        return [(e.id, err) for e, err in load().search_mass(0.0, tolerance=1e6)]

    with_extra = everything()
    _links._database.cache_clear()
    monkeypatch.setitem(sys.modules, "psimodpy", None)
    monkeypatch.setitem(sys.modules, "unimodpy", None)
    try:
        assert everything() == with_extra
    finally:
        _links._database.cache_clear()
    assert len(with_extra) == sum(e.monoisotopic_mass is not None for e in load())


def test_every_dr_line_is_parsed_and_every_link_gives_an_id(db: PtmDatabase) -> None:
    """Each entry's cross_references equal its raw ``DR`` lines in the bundled ptmlist.txt,
    and every PSI-MOD and Unimod reference yields exactly one normalized id.

    Catches: the parser dropping or mangling a DR line (an unexpected database name,
    a missing trailing period, an accession containing "; "), and psimod_ids/unimod_ids
    silently skipping an accession whose format they do not match.
    """
    from importlib.resources import files

    raw: dict[str, list[tuple[str, str]]] = {}
    ac = None
    for line in files("uniprotptmpy").joinpath("data/ptmlist.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("AC   "):
            ac = line[5:].strip()
            raw[ac] = []
        elif line.startswith("DR   ") and ac is not None:
            database, accession = line[5:].rstrip().removesuffix(".").split("; ", 1)
            raw[ac].append((database, accession))
        elif line.startswith("//"):
            ac = None
    failures = []
    for e in db:
        parsed = [(r.database, r.accession) for r in e.cross_references]
        if parsed != raw.get(e.id):
            failures.append(f"{e.id}: parsed {parsed} != file {raw.get(e.id)}")
        for database, ids in (("PSI-MOD", e.psimod_ids), ("Unimod", e.unimod_ids)):
            refs = {a for d, a in parsed if d == database}
            if len(ids) != len(refs):
                failures.append(f"{e.id}: {database} refs {sorted(refs)} gave ids {ids}")
    assert len(raw) == len(db)
    assert not failures, "\n".join(failures)
