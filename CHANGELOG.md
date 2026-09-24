# Changelog

## [Unreleased]

Shared 1.0 API with psimodpy and unimodpy.

### Breaking

- `PtmEntry.proforma_formula` has no spaces: `"HO3P"`, `"H-3N-1"` (was `"H O3 P"`, `"H-3 N-1"`; 487 of 748 entries). Isotopes are bracketed (`"[13C6]"`). The bundled `data/ptmlist.tsv` and `write_tsv` output change with it.
- `PtmDatabase.get_by_id(ac)` parameter renamed to `id`; `get_by_id(ac=...)` still works with a `DeprecationWarning`.
- `get_by_id(True)` / `db[True]` / `True in db` no longer resolve to PTM-0001: `bool` is not an id (`None`, `KeyError`, `False`).
- `PtmDatabase(...)` raises `UniprotPtmError` on a duplicate accession (was: last one silently won). On a duplicate name the first entry keeps the name (was: last).
- Parser errors are typed: a block missing FT or TG, a non-numeric MM/MA, an `ID` inside an open block or a block with no closing `//` raise `UniprotPtmParseError` (a `ValueError`) with the file line. A block missing AC was a bare `KeyError`; it is now skipped with a warning, as is a block with an empty name.
- An unknown feature type (`FT`) no longer aborts the load with `ValueError`: the entry keeps the raw string in `feature_type` (typed `FeatureType | str`) and a warning is issued. An unparseable `CF` is kept raw with a warning; `dict_composition` raises `UniprotPtmParseError` for it (it used to silently skip unknown tokens).
- `download(dest)` reuses an existing file; pass `force=True` to re-download (was: always overwrote).
- Server wire model: `PtmEntry` gains `accession` and `references` (DR lines as `{type, accession, value}`, the psimodpy/unimodpy shape); `PtmSummary` gains `accession`. `/api/health` is a typed `HealthResponse`.
- Classifier `Development Status :: 5 - Production/Stable`.

Migration: replace `get_by_id(ac=x)` with `get_by_id(x)`; code that split `proforma_formula` on spaces should use `dict_composition`; catch `UniprotPtmParseError` (or `ValueError`) around `parse_ptm_list`/`load(path)`; handle `feature_type` possibly being a plain `str` (`str(e.feature_type)` works for both); call `download(force=True)` or `load(refresh=True)` to refresh the cache.

### Added

- `uniprotptmpy.errors`: `UniprotPtmError` and `UniprotPtmParseError(UniprotPtmError, ValueError)`, exported from the package.
- `load(source=None, *, refresh=False)`: `refresh=True` downloads the current release (`download(force=True)`) and parses it.
- `download(dest=None, *, force=False)`.
- `PtmEntry.accession`, equal to `id` (`"PTM-0450"`), as in psimodpy and unimodpy.
- Correction formulas with isotopes (`13C6`, `[13C]6`, `[13C6]`) parse to keys like `"13C"`.

- `PtmDatabase.get(key, default=None)`: returns `db[key]` or `default`, never raises, as in psimodpy and unimodpy.
- `get_by_id`, `db[...]`, `get` and `in` accept an int (`450`) and an unpadded accession (`"450"`, `"PTM-450"`), like psimodpy and unimodpy. Surrounding whitespace is ignored.
- Tests recompute every entry's MM and MA from its correction formula against a frozen NIST table (pyteomics 5.0.1; generator in `tests/reference/`), plus Hypothesis property tests for the lookups. Upstream data errors found: PTM-0745 to PTM-0773 have MM and MA swapped, PTM-0681's MM does not match its CF, PTM-0741's MM is truncated, PTM-0676 has a CF but no masses.

### Fixed

- `db.get_by_id(450)` raised `AttributeError`; it now returns PTM-0450. `db[key]` raises `KeyError` for any key that is not an int or str.
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
