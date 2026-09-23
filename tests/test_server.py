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
from uniprotptmpy.server.models import PtmEntry, PtmSummary  # noqa: E402

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
    assert set(tools) == {"get_by_id", "get_by_name", "search"}
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
