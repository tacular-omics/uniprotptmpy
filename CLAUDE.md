# uniprotptmpy: Claude Code guide

## Project overview

uniprotptmpy parses and queries UniProt's post-translational modification controlled
vocabulary (`ptmlist.txt`, 750 entries in the bundled 2026_03 release). The core
package is pure Python with **no runtime dependencies** and works offline from the
bundled file. An optional `server` extra adds a FastAPI REST API and an MCP server,
deployed on Vercel at `https://uniprot.tacular.dev`, plus a static browser on GitHub
Pages (`https://tacular-omics.github.io/uniprotptmpy/`).

Place in the tacular-omics graph: tier 0, no sibling dependencies. Downstream:
`peff_uniprot_fetcher` (and `peff_digest`) depend on it. `tacular` bundles its **own**
UniProt-PTM copy (`tacular._datagen.uniprot_ptm`) and does not import this package.
Sister vocabulary packages with the same shape: `unimodpy`, `psimodpy`.

## Commands

```bash
just install        # uv sync
just test           # uv run pytest tests            (106 tests, ~2 s, no network)
just lint           # uv run ruff check src tests
just format         # ruff isort fix + ruff format on src and tests
just ty             # uv run ty check src
just check          # lint + ty + test
just build          # uv build, then list the .txt files in the wheel
just check-version  # scripts/release_version.py check
```

CI (`.github/workflows/ci.yml`) also runs `uv run ruff format --check src tests`,
which `just check` does not. Run it before pushing.

Server, locally (needs the extra: `uv sync --extra server`, or `pip install
uniprotptmpy[server]`):

```bash
uv run uvicorn uniprotptmpy.server.app:app --reload     # http://127.0.0.1:8000
```

Run it from the repo root: the dashboard at `/` is read from `docs/index.html`
relative to the working directory (or the source checkout), and 404s otherwise.

## Architecture

```
src/uniprotptmpy/
  __init__.py         # public re-exports + __version__ (the only version source)
  models.py           # PtmEntry, CrossReference, TaxonomicRange (frozen slots dataclasses), FeatureType (StrEnum)
  parser.py           # parse_ptm_list(path) -> PtmDatabase; load(source=None, *, refresh=False, cache=False) reads bundled data/ptmlist.txt
  database.py         # PtmDatabase: id/name indexes, substring search, write_tsv/write_ptmlist
  _formula.py         # parse_ptm_formula("H-3 N-1 O1") -> dict; to_proforma_formula(dict) -> Hill string
  _tabular.py         # write_tsv: one xref_<db> column per cross-reference database present
  _ptmlist_writer.py  # write_ptmlist: re-emits ptmlist.txt entry blocks (no file header)
  _download.py        # download(dest=None, *, force=False): urlretrieve from UniProt FTP to ~/.cache/uniprotptmpy/ptmlist.txt
  data/ptmlist.txt    # bundled UniProt release (source of truth)
  data/ptmlist.tsv    # bundled TSV export; identical to load().write_tsv(...) today
  server/             # optional `server` extra (fastapi, uvicorn, mcp>=2.1.1,<3)
    app.py            # FastAPI `app` + MCPServer `mcp`; loads the DB once at import (shared with the dashboard payload)
    models.py         # pydantic wire models (PtmEntry, PtmSummary, ...) + to_ptm_entry/to_ptm_summary
    dashboard.py      # dashboard_entries(): JSON payload for the browser (/data.json, docs/data.json)
api/index.py          # Vercel entry point: `from uniprotptmpy.server.app import app`
vercel.json           # installCommand `uv pip install '.[server]'`; one function (api/index.py,
                      # maxDuration 10 s, includeFiles docs/**). No rewrites: the Vercel Python
                      # runtime routes every path to the FastAPI app itself
docs/index.html       # static PTM browser; fetches data.json (GitHub Pages and the Vercel `/`)
scripts/export_json.py     # writes docs/data.json (run by .github/workflows/pages.yml; not committed)
scripts/release_version.py # shared tacular-omics version sync/check script; do not edit here
```

Data flow: `ptmlist.txt` -> `parse_ptm_list` builds one `PtmEntry` per `ID ... //`
block (two-letter line codes; `TR`, `KW`, `DR` are multi-valued; trailing periods
stripped) -> `PtmDatabase` indexes by upper-cased `PTM-XXXX` id and lower-cased name.

### HTTP API (`server/app.py`)

| route | returns |
|---|---|
| `GET /` | browser dashboard HTML (404 if `docs/index.html` not found) |
| `GET /data.json` | full dashboard payload, `Cache-Control: max-age=3600` |
| `GET /api/health` | `{ok, package, version, count}` |
| `GET /api/entries?limit=50&offset=0` | `EntryListResponse` (full entries; `limit` 1-500) |
| `GET /api/entries/{id}` | `PtmEntry`; `PTM-0253` or `0253`; 404 if missing |
| `GET /api/entries/by-name/{name}` | `PtmEntry`; case-insensitive exact name; 404 if missing |
| `GET /api/search?q=...&limit=50` | `SearchResponse` of `PtmSummary` (`q` required, `limit` 1-500) |
| `POST /mcp` | MCP streamable HTTP (stateless) |
| `GET /docs`, `/redoc`, `/openapi.json` | FastAPI defaults |

### MCP server

There is no stdio entry point or console script: the MCP server is only served over
HTTP at `/mcp` by the FastAPI app (locally via uvicorn, or at
`https://uniprot.tacular.dev/mcp`). Client setup:
`claude mcp add uniprot-ptm http://localhost:8000/mcp --transport http`.

Tools (all with `outputSchema`, results in `structuredContent`):

- `get_by_id(id)` -> `PtmEntry | None`
- `get_by_name(name)` -> `PtmEntry | None`
- `search(query, limit=25)` -> `list[PtmSummary]`

`_MCPWrapper` builds a fresh `MCPServer` and session manager **per request**, because
Vercel fires no ASGI lifespan events and `StreamableHTTPSessionManager.run()` can run
only once per instance. Keep that; `tests/test_server.py` deliberately calls the app
without entering `TestClient` as a context manager to mimic Vercel.

## Public API

From `uniprotptmpy/__init__.py` (`__all__`):

- Mass search (1.1): `db.search_mass(delta, *, tolerance=0.01, unit="da", site=None, position=None)` over `monoisotopic_mass`, returns `(entry, delta - mass)` closest first; `db.get_by_site(site)`. The index and site/position rules live in `_mass.py`, identical in psimodpy, unimodpy and uniprotptmpy: keep the three copies in sync.
- `entry.get_mass(*, monoisotopic=True)` (1.1) returns `monoisotopic_mass`/`average_mass`, falling back to linked PSI-MOD then Unimod masses when the `link` extra is installed; `search_mass` indexes `get_mass()`.
- Links (1.1), in `_links.py`: `entry.psimod_ids`/`unimod_ids` (no deps); `entry.resolve("psimod"|"unimod")` needs the `link` extra (psimodpy, unimodpy; imported lazily, never at `import uniprotptmpy`). Without the extra it raises `UniprotPtmError` with the install hint. Tests simulate a missing extra by setting `sys.modules["psimodpy"] = None` and clearing `_links._database`.
- Loading: `load(source=None, *, refresh=False, cache=False)`, `parse_ptm_list(path)`, `download(dest=None, *, force=False)`
- Writing: `write_tsv(entries, path, *, delimiter="\t")`, `write_ptmlist(entries, path)`
- Container: `PtmDatabase` with `get_by_id`, `get_by_name`, `search`, `__getitem__`
  (id, then name, else `UniprotPtmKeyError`, a `KeyError`), `__contains__` (same keys, or a `PtmEntry`), `__iter__`, `__len__`, `write_tsv`, `write_ptmlist`
- Errors: `UniprotPtmError`, `UniprotPtmParseError` (also a `ValueError`), `UniprotPtmKeyError` (also a `KeyError`), in `errors.py`
- Models: `PtmEntry` (plus computed `accession`, `dict_composition`, `proforma_formula` like `"HO3P"`),
  `CrossReference`, `TaxonomicRange`, `FeatureType`
- `__version__`

## Conventions

- Python >= 3.12, `from __future__ import annotations`, full type hints, `py.typed` shipped.
- Docstrings: short one-line Google-style; type hints carry the detail.
- Models are frozen `slots` dataclasses with tuples for multi-valued fields.
- Lookups return `None` on a miss; only `PtmDatabase[...]` raises (`UniprotPtmKeyError`, a `KeyError`).
- Ruff line length 120, rules E, W, F, I, B, UP.
- Tests: `tests/test_<module>.py`, session-scoped `db` fixture in `conftest.py`;
  `test_download.py` mocks `urlretrieve`; `test_server.py` skips without fastapi/mcp.
  Use `tmp_path` for file output.

## Gotchas

- `server/app.py` imports `fastapi` and `mcp` at module top; importing
  `uniprotptmpy.server` without the extra fails. The core package must never import it.
- Two different `PtmEntry` classes exist: the dataclass in `models.py` (public) and the
  pydantic wire model in `server/models.py`. Field changes need both, plus
  `to_ptm_entry`, `dashboard.py`, `_tabular.py` and `_ptmlist_writer.py`.
- `search` is a plain substring match over name, id, target and keywords; an empty
  query matches everything. REST enforces `q` min length 1 and `limit` 1-500; the MCP
  `search` tool enforces the same `query` and `limit` bounds.
- `data/ptmlist.tsv` is bundled but nothing reads it and no script regenerates it.
  After updating `ptmlist.txt`, regenerate it with `load().write_tsv(...)`.
- 177 entries have no correction formula (`dict_composition`/`proforma_formula` are
  `None`) and 178 have no monoisotopic mass (PTM-0676 has a formula but no mass).
- `FeatureType.DISULFID` exists but the bundled release has no entries of that type.
- Vercel: without `installCommand` the runtime installs from `pyproject.toml`/`uv.lock`
  with no extras and every request fails with `ModuleNotFoundError: fastapi` (500,
  `FUNCTION_INVOCATION_FAILED`). A catch-all rewrite to `/api/index` makes every request
  404. Keep both as they are.
- `docs/data.json` is built by the Pages workflow, not committed; the Vercel app serves
  the same payload from memory at `/data.json`.

## Releasing

Only the tacular-omics overseer bumps versions or publishes. See `just --list`
(`set-version`, `sync-version`, `check-version`) and `CHANGELOG.md`. The version lives
only in `src/uniprotptmpy/__init__.py` (`__version__`, read by `[tool.hatch.version]`);
`scripts/release_version.py` copies it to `CITATION.cff`. Publishing to PyPI runs from
`.github/workflows/publish.yml` on a published GitHub release.

## Workspace note

This repo is also developed inside the tacular-omics uv workspace; there `uv run` uses
the shared `.venv`. See the workspace CLAUDE.md.
