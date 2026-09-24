"""Shared 1.0 API (aligned with psimodpy and unimodpy): errors, names, formulas, load/download."""

from __future__ import annotations

import inspect
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

import uniprotptmpy
from uniprotptmpy import (
    FeatureType,
    PtmDatabase,
    PtmEntry,
    UniprotPtmError,
    UniprotPtmParseError,
    download,
    load,
    parse_ptm_list,
)
from uniprotptmpy._formula import parse_ptm_formula, to_proforma_formula

_BLOCK = """\
ID   {name}
AC   {ac}
FT   {ft}
TG   Lysine.
CF   {cf}
MM   42.010565
MA   42.04
//
"""


def _write(tmp_path: Path, *blocks: str) -> Path:
    path = tmp_path / "ptmlist.txt"
    path.write_text("header line\n" + "".join(blocks) + "-----\n", encoding="utf-8")
    return path


def _block(name: str = "N6-acetyllysine", ac: str = "PTM-0190", ft: str = "MOD_RES", cf: str = "C2 H2 O1") -> str:
    return _BLOCK.format(name=name, ac=ac, ft=ft, cf=cf)


def _entry(id: str, name: str) -> PtmEntry:
    return PtmEntry(
        id=id,
        name=name,
        feature_type=FeatureType.MOD_RES,
        target="Lysine",
        amino_acid_position=None,
        polypeptide_position=None,
        correction_formula=None,
        monoisotopic_mass=None,
        average_mass=None,
        cellular_location=None,
        taxonomic_ranges=(),
        keywords=(),
        cross_references=(),
    )


# --- errors ---------------------------------------------------------------


def test_error_hierarchy() -> None:
    assert issubclass(UniprotPtmParseError, UniprotPtmError)
    assert issubclass(UniprotPtmParseError, ValueError)
    assert "UniprotPtmError" in uniprotptmpy.__all__
    assert "UniprotPtmParseError" in uniprotptmpy.__all__
    assert "__version__" in uniprotptmpy.__all__


def test_unknown_feature_type_keeps_raw_and_warns(tmp_path: Path) -> None:
    path = _write(tmp_path, _block(ft="NEW_KEY"), _block(name="Other", ac="PTM-0191"))
    with pytest.warns(UserWarning, match="NEW_KEY"):
        db = parse_ptm_list(path)
    assert len(db) == 2
    entry = db["PTM-0190"]
    assert entry.feature_type == "NEW_KEY"
    assert not isinstance(entry.feature_type, FeatureType)
    assert db["PTM-0191"].feature_type is FeatureType.MOD_RES


@pytest.mark.parametrize("drop", ["AC", "ID"])
def test_block_missing_id_or_name_is_skipped_with_warning(tmp_path: Path, drop: str) -> None:
    bad = _block(name="Bad", ac="PTM-0001")
    if drop == "AC":
        bad = bad.replace("AC   PTM-0001\n", "")
    else:
        bad = bad.replace("ID   Bad\n", "ID   \n")
    path = _write(tmp_path, bad, _block())
    with pytest.warns(UserWarning, match="skipp"):
        db = parse_ptm_list(path)
    assert [e.id for e in db] == ["PTM-0190"]


def test_block_missing_target_raises_parse_error(tmp_path: Path) -> None:
    path = _write(tmp_path, _block().replace("TG   Lysine.\n", ""))
    with pytest.raises(UniprotPtmParseError, match="PTM-0190"):
        parse_ptm_list(path)


def test_bad_mass_raises_parse_error_with_line(tmp_path: Path) -> None:
    path = _write(tmp_path, _block().replace("MM   42.010565", "MM   forty-two"))
    with pytest.raises(UniprotPtmParseError, match=r"line \d+"):
        parse_ptm_list(path)


def test_unterminated_block_raises_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "ptmlist.txt"
    path.write_text(_block().replace("//\n", ""), encoding="utf-8")
    with pytest.raises(UniprotPtmParseError, match="unterminated"):
        parse_ptm_list(path)


def test_duplicate_id_raises() -> None:
    with pytest.raises(UniprotPtmError, match="PTM-0001"):
        PtmDatabase([_entry("PTM-0001", "a"), _entry("PTM-0001", "b")])


def test_duplicate_name_first_wins() -> None:
    first, second = _entry("PTM-0001", "Same"), _entry("PTM-0002", "same")
    db = PtmDatabase([first, second])
    assert db.get_by_name("SAME") is first
    assert db["same"] is first
    assert db["PTM-0002"] is second


# --- names and signatures -------------------------------------------------


def test_get_by_id_param_is_named_id() -> None:
    params = inspect.signature(PtmDatabase.get_by_id).parameters
    assert "id" in params
    db = PtmDatabase([_entry("PTM-0001", "a")])
    assert db.get_by_id(id="PTM-0001") is not None


def test_get_by_id_ac_keyword_is_deprecated() -> None:
    db = PtmDatabase([_entry("PTM-0001", "a")])
    with pytest.warns(DeprecationWarning, match="id"):
        assert db.get_by_id(ac="PTM-0001") is db["PTM-0001"]


@pytest.mark.parametrize("key", [True, False, "foo", "", "PTM-", None])
def test_get_by_id_invalid_returns_none(key: object) -> None:
    db = PtmDatabase([_entry("PTM-0000", "zero"), _entry("PTM-0001", "a")])
    assert db.get_by_id(key) is None  # ty: ignore[invalid-argument-type]
    assert key not in db
    with pytest.raises(KeyError):
        db[key]


def test_load_signature() -> None:
    sig = inspect.signature(load)
    assert list(sig.parameters) == ["source", "refresh"]
    assert sig.parameters["refresh"].kind is inspect.Parameter.KEYWORD_ONLY
    assert sig.parameters["refresh"].default is False


def test_download_signature() -> None:
    sig = inspect.signature(download)
    assert list(sig.parameters) == ["dest", "force"]
    assert sig.parameters["force"].kind is inspect.Parameter.KEYWORD_ONLY


def test_download_skips_existing_unless_forced(tmp_path: Path) -> None:
    dest = tmp_path / "ptmlist.txt"
    dest.write_text("cached", encoding="utf-8")
    with patch("uniprotptmpy._download.urllib.request.urlretrieve") as mock:
        assert download(dest) == dest
        mock.assert_not_called()
        download(dest, force=True)
        mock.assert_called_once()


def test_load_refresh_downloads_and_parses(tmp_path: Path) -> None:
    src = _write(tmp_path, _block())
    dest = tmp_path / "cache" / "ptmlist.txt"

    def fake_retrieve(url: str, target: Path) -> None:
        Path(target).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    with (
        patch("uniprotptmpy._download._DEFAULT_DEST", dest),
        patch("uniprotptmpy._download.urllib.request.urlretrieve", side_effect=fake_retrieve) as mock,
    ):
        db = load(refresh=True)
        mock.assert_called_once()
    assert [e.id for e in db] == ["PTM-0190"]


def test_load_refresh_with_source_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load(_write(tmp_path, _block()), refresh=True)


# --- models ---------------------------------------------------------------


def test_accession_equals_id(db: PtmDatabase) -> None:
    for entry in db:
        assert entry.accession == entry.id
        assert isinstance(entry.id, str)


# --- formulas -------------------------------------------------------------


def test_proforma_formula_has_no_spaces(db: PtmDatabase) -> None:
    assert db["PTM-0253"].proforma_formula == "HO3P"
    for entry in db:
        if entry.proforma_formula is not None:
            assert " " not in entry.proforma_formula


def test_proforma_formula_hill_order() -> None:
    assert to_proforma_formula({"N": 1, "H": 3, "C": 2, "O": 1}) == "C2H3NO"
    assert to_proforma_formula({"H": -3, "N": -1}) == "H-3N-1"


def test_isotope_formula_round_trip() -> None:
    comp = parse_ptm_formula("13C6 H-1 15N1")
    assert comp == {"13C": 6, "H": -1, "15N": 1}
    assert to_proforma_formula(comp) == "[13C6]H-1[15N]"
    assert parse_ptm_formula("[13C]6 [2H]-2") == {"13C": 6, "2H": -2}


def test_zero_counts_dropped() -> None:
    assert parse_ptm_formula("C1 C-1 H2") == {"H": 2}
    assert to_proforma_formula({"C": 0, "H": 2}) == "H2"


@pytest.mark.parametrize("cf", ["C2 H3 X?", "C2H3", "C", "(13)C2"])
def test_unparseable_formula_raises(cf: str) -> None:
    with pytest.raises(UniprotPtmParseError, match="CF"):
        parse_ptm_formula(cf)


def test_unparseable_cf_warns_at_load_and_raises_on_access(tmp_path: Path) -> None:
    path = _write(tmp_path, _block(cf="C2 H2 ?1"))
    with pytest.warns(UserWarning, match="PTM-0190"):
        db = parse_ptm_list(path)
    entry = db["PTM-0190"]
    assert entry.correction_formula == "C2 H2 ?1"
    with pytest.raises(UniprotPtmParseError):
        entry.dict_composition  # noqa: B018


def test_bundled_load_emits_no_warnings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert len(load()) == 748


def test_id_inside_open_block_raises_parse_error(tmp_path: Path) -> None:
    path = _write(tmp_path, _block().replace("//\n", ""), _block(name="Other", ac="PTM-0191"))
    with pytest.raises(UniprotPtmParseError, match="closing //"):
        parse_ptm_list(path)
