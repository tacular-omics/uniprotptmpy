"""End-to-end MCP + REST shape tests for the uniprotptmpy server.

The MCP tests deliberately *don't* enter ``TestClient`` as a context manager,
so no ASGI lifespan events fire.  This mirrors how Vercel's serverless
runtime invokes the app — every request is a cold ASGI call — and catches
regressions in our per-request session lifecycle handling alongside
structural guarantees about the new typed responses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")

from fastapi.testclient import TestClient  # noqa: E402

from uniprotptmpy.server.app import app  # noqa: E402
from uniprotptmpy.server.models import MassMatch, PtmEntry, PtmSummary  # noqa: E402

_MCP_HEADERS = {"accept": "application/json, text/event-stream"}
_INIT_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "pytest", "version": "0"},
}


def _parse_sse(body: str) -> dict[str, Any]:
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise AssertionError(f"no data: line in SSE body: {body!r}")


def _mcp(client: TestClient, method: str, params: dict | None = None, *, req_id: int = 1) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    r = client.post("/mcp", json=payload, headers=_MCP_HEADERS)
    assert r.status_code == 200, f"{method} returned {r.status_code}: {r.text}"
    return _parse_sse(r.text)


@pytest.fixture
def mcp_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def known_id() -> str:
    """Pick a real ID from the loaded database."""
    import uniprotptmpy

    db = uniprotptmpy.load()
    return next(iter(db)).id


def test_tools_list_includes_output_schema(mcp_client: TestClient) -> None:
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(mcp_client, "tools/list", req_id=2)
    tools = {t["name"]: t for t in resp["result"]["tools"]}
    assert set(tools) == {"get_by_id", "get_by_name", "search", "search_mass"}
    for name, tool in tools.items():
        assert tool.get("outputSchema"), f"{name} is missing outputSchema"


def test_get_by_id_returns_structured_content(mcp_client: TestClient, known_id: str) -> None:
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "get_by_id", "arguments": {"id": known_id}},
        req_id=2,
    )
    result = resp["result"]
    assert result["content"], "text fallback content missing"
    assert result["content"][0]["type"] == "text"
    sc = result["structuredContent"]
    entry = sc["result"]
    assert entry is not None
    PtmEntry.model_validate(entry)
    assert entry["id"] == known_id


def test_get_by_id_missing_returns_null_result(mcp_client: TestClient) -> None:
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "get_by_id", "arguments": {"id": "PTM-9999999"}},
        req_id=2,
    )
    sc = resp["result"]["structuredContent"]
    assert sc == {"result": None}


def test_search_returns_summaries_not_full_entries(mcp_client: TestClient) -> None:
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search", "arguments": {"query": "phospho", "limit": 3}},
        req_id=2,
    )
    items = resp["result"]["structuredContent"]["result"]
    assert isinstance(items, list)
    assert items, "search should return at least one match for 'phospho'"
    for item in items:
        PtmSummary.model_validate(item)
        assert "cross_references" not in item
        assert "taxonomic_ranges" not in item
        assert "keywords" not in item


def test_rest_get_entry_shape_matches_pydantic(known_id: str) -> None:
    with TestClient(app) as client:
        r = client.get(f"/api/entries/{known_id}")
        assert r.status_code == 200
        PtmEntry.model_validate(r.json())


def test_rest_get_entry_includes_all_tax_ids() -> None:
    with TestClient(app) as client:
        r = client.get("/api/entries/PTM-0005")
        assert r.status_code == 200
        body = PtmEntry.model_validate(r.json())
        assert body.taxonomic_ranges[0].tax_ids == [6447, 91827, 451864]
        assert body.taxonomic_ranges[0].tax_id == 6447
        assert body.taxonomic_ranges[0].tax_names == ["Mollusca", "Gunneridae", "Dikarya"]


def test_rest_search_returns_summaries() -> None:
    with TestClient(app) as client:
        r = client.get("/api/search", params={"q": "phospho", "limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert {"query", "total", "limit", "items"} <= set(body)
        for item in body["items"]:
            PtmSummary.model_validate(item)


@pytest.mark.parametrize("limit", [-1, 0, 501])
def test_search_rejects_out_of_range_limit(mcp_client: TestClient, limit: int) -> None:
    """The MCP ``search`` tool enforces the same 1-500 ``limit`` bound as REST."""
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search", "arguments": {"query": "phospho", "limit": limit}},
        req_id=2,
    )
    assert resp["result"]["isError"] is True
    assert "structuredContent" not in resp["result"] or not resp["result"]["structuredContent"]


def test_search_accepts_max_limit(mcp_client: TestClient) -> None:
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search", "arguments": {"query": "PTM-", "limit": 500}},
        req_id=2,
    )
    assert len(resp["result"]["structuredContent"]["result"]) == 500


def test_search_rejects_empty_query(mcp_client: TestClient) -> None:
    """The MCP ``search`` tool rejects an empty query, like REST's ``q`` min length 1."""
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search", "arguments": {"query": ""}},
        req_id=2,
    )
    assert resp["result"]["isError"] is True
    assert "structuredContent" not in resp["result"] or not resp["result"]["structuredContent"]


def test_server_import_parses_data_file_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing the server loads the bundled ptmlist.txt once, not once per consumer."""
    import importlib
    import sys

    import uniprotptmpy

    app_module = sys.modules["uniprotptmpy.server.app"]
    dashboard_module = sys.modules["uniprotptmpy.server.dashboard"]

    calls = 0
    real_load = uniprotptmpy.load

    def counting_load(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return real_load(*args, **kwargs)

    monkeypatch.setattr(uniprotptmpy, "load", counting_load)
    monkeypatch.setattr(dashboard_module, "load", counting_load, raising=False)
    try:
        importlib.reload(app_module)
        assert calls == 1
    finally:
        monkeypatch.undo()
        importlib.reload(app_module)


def test_rest_entry_has_accession_and_references() -> None:
    client = TestClient(app)
    body = client.get("/api/entries/PTM-0253").json()
    assert body["accession"] == body["id"] == "PTM-0253"
    assert body["proforma_formula"] == "HO3P"
    refs = body["references"]
    assert refs, "PTM-0253 has DR lines"
    assert {"type", "accession", "value"} <= set(refs[0])
    assert [(r["type"], r["accession"]) for r in refs] == [
        (x["database"], x["accession"]) for x in body["cross_references"]
    ]
    summary = client.get("/api/search", params={"q": "PTM-0253"}).json()["items"][0]
    assert summary["accession"] == "PTM-0253"


@pytest.mark.parametrize("bad", ["foo", "PTM-", "true"])
def test_rest_unparseable_id_is_404(bad: str) -> None:
    assert TestClient(app).get(f"/api/entries/{bad}").status_code == 404


def test_dashboard_rows_are_typed() -> None:
    from typing import get_type_hints

    from uniprotptmpy.server.dashboard import DashboardRow, dashboard_entries

    keys = set(get_type_hints(DashboardRow))
    rows = dashboard_entries()
    assert rows and set(rows[0]) == keys


def test_to_ptm_entry_survives_unparseable_cf() -> None:
    from dataclasses import replace

    from uniprotptmpy import load
    from uniprotptmpy.server.models import to_ptm_entry

    entry = replace(load()["PTM-0450"], correction_formula="C2 X? H1")
    wire = to_ptm_entry(entry)
    assert wire.correction_formula == "C2 X? H1"
    assert wire.dict_composition is None
    assert wire.proforma_formula is None


def test_dashboard_taxon_ids_match_library() -> None:
    from uniprotptmpy import load
    from uniprotptmpy.server.dashboard import dashboard_entries

    db = load()
    rows = dashboard_entries(db)
    assert len(rows) == len(db) == 750
    for row in rows:
        entry = db[row["id"]]
        assert [t["tax_ids"] for t in row["taxonomic_ranges"]] == [list(tr.tax_ids) for tr in entry.taxonomic_ranges]
    ranges = next(r for r in rows if r["id"] == "PTM-0005")["taxonomic_ranges"]
    assert [i for t in ranges for i in t["tax_ids"]] == [6447, 91827, 451864]


# --- search-mass and by-site (#76) ---


def _expected_mass_rows(**kwargs: Any) -> list[tuple[str, float]]:
    from uniprotptmpy import load

    return [(e.id, err) for e, err in load().search_mass(79.9663, tolerance=0.01, **kwargs)]


def test_rest_search_mass_matches_library() -> None:
    expected = _expected_mass_rows(site="STY")
    assert expected, "79.9663 on STY should hit phosphorylations"
    with TestClient(app) as client:
        r = client.get("/api/search-mass", params={"delta": 79.9663, "tolerance": 0.01, "site": "STY"})
    assert r.status_code == 200
    body = r.json()
    assert [(i["id"], i["error"]) for i in body["items"]] == expected
    assert body["total"] == len(expected)
    for item in body["items"]:
        MassMatch.model_validate(item)
        assert "cross_references" not in item


def test_rest_search_mass_default_tolerance_and_limit() -> None:
    with TestClient(app) as client:
        body = client.get("/api/search-mass", params={"delta": 79.9663}).json()
        assert body["tolerance"] == 0.01
        capped = client.get("/api/search-mass", params={"delta": 79.9663, "tolerance": 5, "limit": 2}).json()
    assert len(capped["items"]) == 2
    assert capped["total"] > 2


def test_rest_search_mass_position() -> None:
    from uniprotptmpy import load

    expected = [e.id for e, _ in load().search_mass(79.9663, site="S", position="protein n-term")]
    with TestClient(app) as client:
        body = client.get(
            "/api/search-mass", params={"delta": 79.9663, "site": "S", "position": "protein n-term"}
        ).json()
    assert [i["id"] for i in body["items"]] == expected


@pytest.mark.parametrize(
    "params",
    [
        {"delta": 79.9663, "site": "X9"},
        {"delta": 79.9663, "position": "nowhere"},
        {"delta": 79.9663, "tolerance": -0.1},
        {"delta": 79.9663, "limit": 0},
        {"delta": 79.9663, "limit": 501},
        {"delta": "nan"},
        {},
    ],
)
def test_rest_search_mass_invalid_is_422(params: dict) -> None:
    with TestClient(app) as client:
        assert client.get("/api/search-mass", params=params).status_code == 422


def test_rest_by_site_matches_library() -> None:
    from uniprotptmpy import load

    expected = [e.id for e in load().get_by_site("S")]
    assert expected
    with TestClient(app) as client:
        r = client.get("/api/entries/by-site/S")
        lower = client.get("/api/entries/by-site/s")
    assert r.status_code == 200
    body = r.json()
    assert [i["id"] for i in body["items"]] == expected
    assert body["total"] == len(expected)
    for item in body["items"]:
        PtmSummary.model_validate(item)
    assert [i["id"] for i in lower.json()["items"]] == expected


@pytest.mark.parametrize("site", ["X9", "B", "STY", "1"])
def test_rest_by_site_unknown_is_422(site: str) -> None:
    with TestClient(app) as client:
        assert client.get(f"/api/entries/by-site/{site}").status_code == 422


def test_rest_by_site_terminus_is_empty_not_error() -> None:
    with TestClient(app) as client:
        r = client.get("/api/entries/by-site/N-term")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_rest_search_offset_pages_past_first_results() -> None:
    with TestClient(app) as client:
        full = client.get("/api/search", params={"q": "PTM-", "limit": 500}).json()
        page = client.get("/api/search", params={"q": "PTM-", "limit": 500, "offset": 500}).json()
        bad = client.get("/api/search", params={"q": "PTM-", "offset": -1})
    assert full["total"] > 500
    assert page["total"] == full["total"]
    assert len(page["items"]) == full["total"] - 500
    assert page["items"][0]["id"] not in {i["id"] for i in full["items"]}
    assert bad.status_code == 422


def test_mcp_search_mass_matches_rest(mcp_client: TestClient) -> None:
    args = {"delta": 79.9663, "tolerance": 0.01, "site": "STY", "limit": 500}
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(mcp_client, "tools/call", {"name": "search_mass", "arguments": args}, req_id=2)
    rows = resp["result"]["structuredContent"]["result"]
    rest = mcp_client.get("/api/search-mass", params=args).json()["items"]
    assert rows == rest
    assert [(r["id"], r["error"]) for r in rows] == _expected_mass_rows(site="STY")
    for row in rows:
        MassMatch.model_validate(row)


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 501}, "limit"),
        ({"tolerance": -1}, "tolerance"),
        ({"site": "X9"}, "unknown site 'X9'"),
        ({"position": "nowhere"}, "unknown position 'nowhere'"),
    ],
)
def test_mcp_search_mass_rejects_bad_arguments(mcp_client: TestClient, extra: dict, expected: str) -> None:
    """The text must name what was rejected.

    ``isError`` alone passes on a tree where the tool does not exist at all: an unknown
    tool name also comes back as an error result (with ``Unknown tool: ...``), so only the
    message distinguishes a rejected argument from a missing tool or a crash.
    """
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search_mass", "arguments": {"delta": 79.9663, **extra}},
        req_id=2,
    )
    assert resp["result"]["isError"] is True
    text = resp["result"]["content"][0]["text"]
    assert expected in text, text
    assert text != "Error executing tool search_mass"


def test_mcp_search_mass_unknown_site_message_reaches_the_caller(mcp_client: TestClient) -> None:
    """An unknown site is a failure we anticipate, so our own text must reach the model.

    The MCP SDK gives the caller only ``Error executing tool <name>`` for an exception it
    treats as a crash, and keeps the message only for a ``ToolError``. So this asserts the
    library's own wording, which is the part a model can act on.
    """
    _mcp(mcp_client, "initialize", _INIT_PARAMS)
    resp = _mcp(
        mcp_client,
        "tools/call",
        {"name": "search_mass", "arguments": {"delta": 79.9663, "site": "X9"}},
        req_id=2,
    )
    text = resp["result"]["content"][0]["text"]
    assert resp["result"]["isError"] is True
    assert "unknown site 'X9'" in text, text
    assert "use residue letters" in text, text
    # The same call through REST already names it; MCP must not say less.
    detail = mcp_client.get("/api/search-mass", params={"delta": 79.9663, "site": "X9"}).json()["detail"]
    assert "unknown site 'X9'" in detail


# --- Unknown query parameters (one app-wide dependency, not per-route code) ---

#: One case per API route: path, a request the route accepts, and the names it declares.
#: The declared names are written out here rather than read from the app, so a parameter
#: renamed in the app fails this table instead of agreeing with itself.
_ROUTE_CASES = [
    ("/api/health", {}, set()),
    ("/api/entries", {"limit": 2}, {"limit", "offset"}),
    ("/api/entries/PTM-0253", {}, set()),
    ("/api/entries/by-name/Phosphoserine", {}, set()),
    ("/api/entries/by-site/S", {}, set()),
    ("/api/search", {"q": "phospho"}, {"q", "limit", "offset"}),
    ("/api/search-mass", {"delta": 79.9663}, {"delta", "tolerance", "site", "position", "limit"}),
]


@pytest.mark.parametrize(("path", "params", "declared"), _ROUTE_CASES)
def test_rest_unknown_query_parameter_is_422(path: str, params: dict, declared: set[str]) -> None:
    """Every API route names the unknown parameter and lists what it accepts."""
    with TestClient(app) as client:
        r = client.get(path, params={**params, "bogus": "1"})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "unknown query parameter 'bogus'" in detail, detail
    expected_tail = ", ".join(sorted(declared)) if declared else "no query parameters"
    assert detail.endswith(f"accepts: {expected_tail}"), detail


@pytest.mark.parametrize(("path", "params", "declared"), _ROUTE_CASES)
def test_rest_known_query_parameters_still_work(path: str, params: dict, declared: set[str]) -> None:
    """The accepted request is unchanged, and no declared name is treated as unknown.

    A declared name may still be rejected on its own merits (``site=1`` is not a residue),
    so this asserts the name is not called unknown rather than asserting a 200.
    """
    with TestClient(app) as client:
        assert client.get(path, params=params).status_code == 200
        for name in declared:
            r = client.get(path, params={**params, name: params.get(name, 1)})
            assert "unknown query parameter" not in r.text, f"{path} called its own {name!r} unknown"


def test_rest_unknown_query_parameter_names_every_unknown() -> None:
    with TestClient(app) as client:
        r = client.get("/api/search-mass", params={"delta": 79.9663, "unit": "ppm", "tolernce": "0.001"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "unknown query parameters 'tolernce', 'unit'" in detail, detail
    assert "accepts: delta, limit, position, site, tolerance" in detail, detail


def test_rest_misspelled_parameter_no_longer_falls_back_to_the_default() -> None:
    """``tolernce=0.001`` used to return 200 with the 0.01 default, silently."""
    with TestClient(app) as client:
        assert client.get("/api/search-mass", params={"delta": 79.9663, "tolernce": "0.001"}).status_code == 422
        ok = client.get("/api/search-mass", params={"delta": 79.9663, "tolerance": "0.001"})
    assert ok.status_code == 200
    assert ok.json()["tolerance"] == 0.001


def test_dashboard_routes_keep_ignoring_unknown_query_parameters() -> None:
    """Deliberate exemption, not an oversight.

    ``/`` and ``/data.json`` are opened in a browser, where a shared link can carry a
    tracking parameter; a 422 would hide the page over a harmless extra. The API routes
    above are machine-facing, where a silently ignored parameter is the worse failure.
    """
    with TestClient(app) as client:
        assert client.get("/", params={"utm_source": "newsletter"}).status_code == 200
        assert client.get("/data.json", params={"utm_source": "newsletter"}).status_code == 200
