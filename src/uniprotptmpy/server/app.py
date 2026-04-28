"""FastAPI app exposing the uniprotptmpy database as REST and MCP."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import uniprotptmpy
from uniprotptmpy.server.dashboard import dashboard_entries
from uniprotptmpy.server.models import (
    EntryListResponse,
    PtmEntry,
    PtmSummary,
    SearchResponse,
    to_ptm_entry,
    to_ptm_summary,
)

_db = uniprotptmpy.load()
_PACKAGE = "uniprotptmpy"


# Render dashboard payload once at import time.
_DATA_JSON = json.dumps(dashboard_entries(), separators=(",", ":")).encode()


# Locate the static dashboard. On Vercel the function bundle includes ``docs/``
# (see vercel.json includeFiles); locally it lives at the repo root.
def _load_dashboard_html() -> str | None:
    for candidate in (
        Path.cwd() / "docs" / "index.html",
        Path(__file__).resolve().parents[3] / "docs" / "index.html",
    ):
        try:
            if candidate.is_file():
                return candidate.read_text()
        except OSError:
            continue
    return None


_DASHBOARD_HTML = _load_dashboard_html()


def _split_residues(residues: str | None) -> list[str] | None:
    if residues is None:
        return None
    parts = [r.strip() for r in residues.split(",") if r.strip()]
    return parts or None


# ---------------------------------------------------------------------------
# MCP server (mounted at /, exposes its own /mcp route)
# ---------------------------------------------------------------------------


def _build_mcp() -> FastMCP:
    mcp = FastMCP(
        _PACKAGE,
        instructions="Query the UniProt PTM controlled vocabulary.",
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    def get_by_id(id: str) -> PtmEntry | None:
        """Look up a PTM by accession. Accepts ``"PTM-0450"`` or bare ``"0450"``."""
        entry = _db.get_by_id(id)
        return to_ptm_entry(entry) if entry else None

    @mcp.tool()
    def get_by_name(name: str) -> PtmEntry | None:
        """Look up a PTM by exact name (case-insensitive)."""
        entry = _db.get_by_name(name)
        return to_ptm_entry(entry) if entry else None

    @mcp.tool()
    def search(query: str, limit: int = 25) -> list[PtmSummary]:
        """Free-text search over name, ID, target, and keywords.

        Returns up to ``limit`` lightweight summaries.  Call ``get_by_id`` on
        any returned ``id`` to fetch the full entry.
        """
        return [to_ptm_summary(e) for e in _db.search(query)[:limit]]

    @mcp.tool()
    def find(
        text: str | None = None,
        mass_min: float | None = None,
        mass_max: float | None = None,
        mass_type: str = "mono",
        residues: list[str] | None = None,
        feature_type: str | None = None,
        keyword: str | None = None,
        taxon_id: int | None = None,
        limit: int = 25,
    ) -> list[PtmSummary]:
        """Fine-grained AND-combined search across name/ID/target/keywords,
        mass range, residue (target) codes, feature type, keyword, and taxon id.

        Returns up to ``limit`` lightweight summaries.
        """
        mt: str = mass_type if mass_type in ("mono", "avg") else "mono"
        results = _db.find(
            text=text,
            mass_min=mass_min,
            mass_max=mass_max,
            mass_type=mt,  # type: ignore[arg-type]
            residues=residues,
            feature_type=feature_type,
            keyword=keyword,
            taxon_id=taxon_id,
            limit=limit,
        )
        return [to_ptm_summary(e) for e in results]

    return mcp


# Module-level instance for inspection / re-export.
mcp = _build_mcp()


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------


# Vercel doesn't fire ASGI lifespan events, and StreamableHTTPSessionManager.run()
# can only be called once per instance, so we build a fresh FastMCP per request.
class _MCPWrapper:
    async def __call__(self, scope, receive, send) -> None:
        m = _build_mcp()
        http_app = m.streamable_http_app()
        async with m.session_manager.run():
            await http_app(scope, receive, send)


app = FastAPI(
    title="uniprotptmpy API",
    description="REST + MCP interface to the UniProt PTM controlled vocabulary.",
    version=uniprotptmpy.__version__,
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    if _DASHBOARD_HTML is None:
        raise HTTPException(status_code=404, detail="Dashboard not bundled with deployment")
    return _DASHBOARD_HTML


@app.get("/data.json", include_in_schema=False)
def dashboard_data() -> Response:
    return Response(
        content=_DATA_JSON,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "package": _PACKAGE,
        "version": uniprotptmpy.__version__,
        "count": len(_db),
    }


@app.get("/api/entries", response_model=EntryListResponse)
def list_entries(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EntryListResponse:
    entries = list(_db)
    page = entries[offset : offset + limit]
    return EntryListResponse(
        total=len(entries),
        limit=limit,
        offset=offset,
        items=[to_ptm_entry(e) for e in page],
    )


@app.get("/api/entries/{id}", response_model=PtmEntry)
def get_entry(id: str) -> PtmEntry:
    entry = _db.get_by_id(id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No entry for id={id!r}")
    return to_ptm_entry(entry)


@app.get("/api/entries/by-name/{name}", response_model=PtmEntry)
def get_entry_by_name(name: str) -> PtmEntry:
    entry = _db.get_by_name(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No entry for name={name!r}")
    return to_ptm_entry(entry)


@app.get("/api/search", response_model=SearchResponse)
def search_entries(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
) -> SearchResponse:
    results = _db.search(q)
    return SearchResponse(
        query=q,
        total=len(results),
        limit=limit,
        items=[to_ptm_summary(e) for e in results[:limit]],
    )


@app.get("/api/find", response_model=list[PtmSummary])
def find_entries(
    text: str | None = Query(None),
    mass_min: float | None = Query(None),
    mass_max: float | None = Query(None),
    mass_type: str = Query("mono", pattern="^(mono|avg)$"),
    residues: str | None = Query(None, description="Comma-separated residue codes"),
    feature_type: str | None = Query(None),
    keyword: str | None = Query(None),
    taxon_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> list[PtmSummary]:
    results = _db.find(
        text=text,
        mass_min=mass_min,
        mass_max=mass_max,
        mass_type=mass_type,  # type: ignore[arg-type]
        residues=_split_residues(residues),
        feature_type=feature_type,
        keyword=keyword,
        taxon_id=taxon_id,
        limit=limit,
    )
    return [to_ptm_summary(e) for e in results]


# Mount MCP at the root; its inner app exposes /mcp.
app.mount("/", _MCPWrapper())
