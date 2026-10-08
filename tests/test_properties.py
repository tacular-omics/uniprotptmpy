"""Property tests: `[]`, `get` and `in` agree for every key form, and never crash."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import uniprotptmpy

_DB = uniprotptmpy.load()
_IDS = sorted(int(e.id.removeprefix("PTM-")) for e in _DB)
_NAMES = [e.name for e in _DB]
_SETTINGS = settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _id_forms(n: int) -> st.SearchStrategy[object]:
    return st.sampled_from([n, str(n), f"{n:04d}", f"PTM-{n:04d}", f"ptm-{n:04d}", f"PTM-{n}", f" PTM-{n:04d} "])


_existing = st.sampled_from(_IDS).flatmap(_id_forms)
_names = st.sampled_from(_NAMES).flatmap(lambda s: st.sampled_from([s, s.upper(), s.lower()]))
_junk = st.one_of(
    st.integers(min_value=-(10**6), max_value=10**6).flatmap(_id_forms),
    st.text(max_size=20),
    st.text(max_size=8).map(lambda s: f"PTM-{s}"),
    st.none(),
    st.floats(allow_nan=False),
    st.tuples(st.integers()),
)
_keys = st.one_of(_existing, _names, _junk)


def _getitem(key: object):
    try:
        return _DB[key]
    except KeyError:
        return None


@_SETTINGS
@given(_keys)
def test_contains_getitem_and_get_agree(key):
    entry = _DB.get(key)  # never raises
    assert _getitem(key) is entry
    assert (key in _DB) is (entry is not None)


def test_every_entry_resolves_by_every_key() -> None:
    """Every entry, by every key form the API takes, returns that same entry.

    Catches: a name that shadows or is shadowed by another entry's accession in ``[]``
    (id is tried first), a case-insensitive name collision that hides an entry, an
    accession form (unpadded, lowercase prefix, padded, int, whitespace) that misses
    for some ids, and a TG residue dropped from the get_by_site index.
    """
    letters = {
        "Alanine": "A", "Arginine": "R", "Asparagine": "N", "Aspartate": "D", "Cysteine": "C",
        "Glutamate": "E", "Glutamine": "Q", "Glycine": "G", "Histidine": "H", "Isoleucine": "I",
        "Leucine": "L", "Lysine": "K", "Methionine": "M", "Phenylalanine": "F", "Proline": "P",
        "Pyrrolysine": "O", "Selenocysteine": "U", "Serine": "S", "Threonine": "T",
        "Tryptophan": "W", "Tyrosine": "Y", "Valine": "V",
    }  # fmt: skip
    by_site = {letter: set(map(id, _DB.get_by_site(letter))) for letter in set(letters.values())}
    failures = []
    for e in _DB:
        n = int(e.id.removeprefix("PTM-"))
        keys = [e.id, e.accession, n, str(n), f"{n:04d}", f"ptm-{n:04d}", f"PTM-{n}", f" {e.id} "]
        for key in keys:
            if _DB.get_by_id(key) is not e or _DB.get(key) is not e or key not in _DB or _getitem(key) is not e:
                failures.append(f"{e.id}: id key {key!r}")
        for key in (e.name, e.name.upper(), e.name.lower()):
            if _DB.get_by_name(key) is not e or _getitem(key) is not e:
                failures.append(f"{e.id}: name key {key!r}")
        if e not in _DB:
            failures.append(f"{e.id}: entry object not `in` db")
        for residue in e.target.split("-"):
            for letter in "ND" if residue == "Asparagine or Aspartate" else letters.get(residue, ""):
                if id(e) not in by_site[letter]:
                    failures.append(f"{e.id}: missing from get_by_site({letter!r}) ({e.target})")
    assert not failures, "\n".join(failures)


@_SETTINGS
@given(st.text(max_size=30))
def test_search_never_crashes(query):
    results = _DB.search(query)
    assert isinstance(results, list)
    assert all(r in _DB for r in results)


def test_len_matches_iteration():
    assert len(_DB) == len(list(_DB)) == len(set(_IDS))
