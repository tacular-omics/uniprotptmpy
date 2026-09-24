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


@_SETTINGS
@given(_existing)
def test_every_id_form_resolves(key):
    assert _DB.get(key) is not None


@_SETTINGS
@given(_names)
def test_every_name_resolves(name):
    assert _DB.get(name) is not None


@_SETTINGS
@given(st.sampled_from(_IDS))
def test_entry_ids_round_trip(n):
    entry = _DB[n]
    assert _DB[f"PTM-{n:04d}"] is entry
    assert entry in _DB


@_SETTINGS
@given(st.text(max_size=30))
def test_search_never_crashes(query):
    results = _DB.search(query)
    assert isinstance(results, list)
    assert all(r in _DB for r in results)


def test_len_matches_iteration():
    assert len(_DB) == len(list(_DB)) == len(set(_IDS))
