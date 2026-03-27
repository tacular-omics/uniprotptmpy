from __future__ import annotations

from uniprotptmpy._formula import parse_ptm_formula, to_proforma_formula


# --- parse_ptm_formula ---


def test_parse_empty_string() -> None:
    assert parse_ptm_formula("") == {}


def test_parse_single_positive() -> None:
    assert parse_ptm_formula("O1") == {"O": 1}


def test_parse_single_negative() -> None:
    assert parse_ptm_formula("H-2") == {"H": -2}


def test_parse_mixed() -> None:
    result = parse_ptm_formula("C2 H3 N-1 O1")
    assert result == {"C": 2, "H": 3, "N": -1, "O": 1}


def test_parse_cancellation() -> None:
    """Elements that sum to zero are excluded from the result."""
    assert parse_ptm_formula("H1 H-1") == {}


# --- to_proforma_formula ---


def test_proforma_single_count_one() -> None:
    assert to_proforma_formula({"O": 1}) == "O"


def test_proforma_hill_order() -> None:
    """Carbon first, hydrogen second, then alphabetical."""
    result = to_proforma_formula({"N": 1, "H": 3, "C": 2, "O": 1})
    assert result == "C2 H3 N O"


def test_proforma_no_carbon() -> None:
    """Without carbon, all elements are alphabetical."""
    result = to_proforma_formula({"O": 1, "N": 2})
    assert result == "N2 O"


def test_proforma_empty() -> None:
    assert to_proforma_formula({}) == ""
