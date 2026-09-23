# Changelog

## [Unreleased]

### Fixed

- `PtmDatabase` has `__contains__`: `key in db` accepts the same keys as `db[key]` (`PTM-0450`, bare `0450`, any case, or a name) and returns `False` for anything else instead of scanning entries. `entry in db` still works for entries.
- The MCP `search` tool rejects an empty `query`, like the REST `/api/search` endpoint; it used to return the first `limit` entries.

## [0.2.2] (2026-09-23)

### Fixed

- The MCP `search` tool rejects a `limit` outside 1-500, like the REST `/api/search` endpoint; `-1` used to return nearly every entry.
- The server parses the bundled `ptmlist.txt` once at import instead of twice (the dashboard payload reuses the loaded database); `dashboard_entries()` takes an optional `db`.
- `just lint` and `just format` cover `tests` as well as `src`, matching CI.
- Removed the unused `requirements.txt`; Vercel installs the `server` extra via `installCommand` in `vercel.json`.

## [0.2.1] (2026-09-23)

### Added

- Releases are archived on Zenodo (`.zenodo.json`); no code changes.

## [0.2.0] (2026-09-23)

### Added

- `write_ptmlist` writes entries back to the `ptmlist.txt` format.
- TSV/CSV writer for PTM entries; `cross_references` is split into one column per database.
- Online UniProt PTM browser (GitHub Pages) with search, sort, filter and a full detail view.
- FastAPI REST API and MCP server (`server` extra), deployable to Vercel, which also serves the browser dashboard at the root.

### Changed

- **Breaking for the `server` extra:** the MCP server was ported from FastMCP (mcp 1.x) to `MCPServer` (mcp 2.x); it now requires mcp 2.
- MCP tools return typed responses (`structuredContent` with an `outputSchema`).
- Releases publish to PyPI by trusted publishing; the version lives only in `uniprotptmpy.__version__`, with `CITATION.cff` kept in sync.

### Fixed

- The dashboard HTML is read as UTF-8, so it loads on Windows.
- The MCP session manager is created per request, fixing session reuse errors on Vercel.

## [0.1.2] (2026-03-27)

- Packaging and build fixes.

## [0.1.1] (2026-03-27)

- Packaging fixes; development dependencies moved to dependency groups.

## [0.1.0] (2026-03-26)

* First release on PyPI.
