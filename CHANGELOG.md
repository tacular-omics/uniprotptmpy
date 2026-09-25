# Changelog

## [Unreleased]

### Added

- Browser site (`docs/index.html`): mass search. Enter a signed delta mass, a tolerance in Da or ppm (ppm is relative to a precursor mass you enter) and monoisotopic or average mass; it combines with the text search, adds a sortable Δ error column (closest first) and keeps its state in the URL (`?mass=42.0106&tol=0.01&unit=da`). Same matching rule as `search_mass()`. `scripts/test_mass_search.py` checks it headless against `search_mass()` (needs Playwright).

### Changed

- The source distribution now contains only the source, tests and the README, changelog, citation and license files: no paper, docs, lockfile or repository tooling.

## [1.1.0] (2026-09-24)

Additive only: nothing that worked in 1.0 changes behaviour.

### Added

- `load(cache=True)`: parse the bundled ptmlist.txt once per process and return that same database on later `load(cache=True)` calls. The database is shared by every such caller: do not modify it. Combining `cache=True` with `source` or `refresh=True` raises `ValueError`. The default (`cache=False`) still parses anew on each call.
- `UniprotPtmKeyError(UniprotPtmError, KeyError)`, exported: `db[key]` raises it on a miss. It is still a `KeyError`, not a `ValueError` (so `except KeyError` and `db.get` work as before) and `args[0]` is still the key.
- `search_mass(delta, *, tolerance=0.01, tolerance_unit="da", site=None, position=None) -> list[tuple[entry, float]]`: entries whose `monoisotopic_mass` (mass difference) is within `tolerance` of `delta`, as `(entry, error)` pairs with `error = delta - mass`, closest first (ties in mass, then file order). `tolerance_unit` accepts only `"da"` (exact, lowercase): ppm is not offered because a ppm window on a delta mass is ill-defined, and the keyword keeps the call shape of `tacular.tolerance` so units can be added later. Both window edges are inclusive. Entries without a mass are skipped. `site` is one or more residue letters (`"S"`, `"STY"`, any case; any of them matches, while `get_by_site` takes exactly one) or `"N-term"`/`"C-term"`, matched against the target residue(s) (`target`; crosslinks list each residue, "Asparagine or Aspartate" is N and D, "Undefined" matches no residue). `position` is where the residue was observed: `"anywhere"`, `"peptide n-term"`, `"peptide c-term"`, `"protein n-term"`, `"protein c-term"` (case-insensitive; `"Any N-term"`/`"Any C-term"` are aliases for the peptide ones); it is matched against the polypeptide position (`position`: Anywhere, N-terminal, C-terminal, with or without Protein core); UniProt does not distinguish protein from peptide terminus for these, so an N-terminal PTM matches both `"peptide n-term"` and `"protein n-term"`. Entries with no usable position count as anywhere. A modification of the terminus itself matches any residue at that terminus. A sorted mass index is built on the first call, and each search is a bisect. A bad `site`, `position`, `tolerance_unit`, `delta` or `tolerance` raises `UniprotPtmError`.
- `get_by_site(site)`: entries whose target includes residue `site` (one letter, case-insensitive), in file order. It takes exactly one residue (`search_mass(site=)` takes several). Unknown or non-string input returns `[]`.
- `PtmEntry.get_mass(*, monoisotopic=True) -> float | None`: the mass difference in Da, `monoisotopic_mass` (default) or `average_mass` (`monoisotopic=False`), with the same keyword as tacular 2.0's `get_mass`. The old attributes stay. `search_mass` uses it. It is only UniProt's own mass (`MM`/`MA`), or `None`: it never fills a missing mass from a linked PSI-MOD or Unimod entry, with or without the `link` extra, so `search_mass` gives the same results either way. For a linked mass, call `resolve()` and pick the entry yourself; it is not automatic because links do not always carry the same mass (PTM-0133, glycine radical, links to a PSI-MOD term with mass difference 0.0; some links are wrong; GPI-anchor links give only the core).
- `PtmEntry.psimod_ids` / `PtmEntry.unimod_ids`: linked accessions from `cross_references`, normalized to `"MOD:00046"` / `"UNIMOD:21"` (each accepts only its own prefix or bare digits, so a stray `"UNIMOD:46"` under PSI-MOD is ignored), in order and without duplicates (512 entries link to PSI-MOD, 252 to Unimod). They need no extra dependency.
- `PtmEntry.resolve("psimod" | "unimod")` returns the linked `psimodpy.PsiModEntry` / `unimodpy.UnimodEntry` objects from each package's bundled data, loaded once per process. It skips ids the linked release lacks. It needs the new optional extra `uniprotptmpy[link]` (`psimodpy>=1.1,<2`, `unimodpy>=1.1,<2`); without the extra it raises `UniprotPtmError` saying to install it, and another target also raises `UniprotPtmError`.

### Changed

- `search()` is several times faster: each entry's lowercased name, id, target and keywords are joined once when the database is built, so a query is one substring test per entry instead of lowercasing every field on every call. Results and their order are unchanged (tested against the 1.0 algorithm).
- `import uniprotptmpy` no longer imports `urllib.request` (and with it `http.client`, `ssl`, `email`): it is imported when `download()` runs, saving about 30 ms at import.

## [1.0.0] (2026-09-23)

First stable release: the public API is now stable and follows semantic versioning.

Shared 1.0 API with psimodpy and unimodpy.

### Breaking

- `PtmEntry.proforma_formula` has no spaces: `"HO3P"`, `"H-3N-1"` (was `"H O3 P"`, `"H-3 N-1"`; 487 of 748 entries). Isotopes are bracketed (`"[13C6]"`). The bundled `data/ptmlist.tsv` and `write_tsv` output change with it.
- `PtmDatabase.get_by_id(ac)` parameter renamed to `id`; `get_by_id(ac=...)` still works with a `DeprecationWarning`.
- `get_by_id(True)` / `db[True]` / `True in db` no longer resolve to PTM-0001: `bool` is not an id (`None`, `KeyError`, `False`).
- `PtmDatabase(...)` raises `UniprotPtmError` on a duplicate accession (was: last one silently won). On a duplicate name the first entry keeps the name (was: last).
- Parser errors are typed: a non-numeric MM/MA, an `ID` inside an open block or a block with no closing `//` raise `UniprotPtmParseError` (a `ValueError`) with the file line; a duplicate accession raises `UniprotPtmError` with the line. A block missing AC, FT or TG was a bare `KeyError`; it is now skipped with a `UserWarning`, as is a block with an empty name.
- An unknown feature type (`FT`) no longer aborts the load with `ValueError`: the entry keeps the raw string in `feature_type` (typed `FeatureType | str`) and a warning is issued. An unparseable `CF` is kept raw with a warning; `dict_composition` and `proforma_formula` are `None` for it (they used to silently skip unknown tokens).
- `download(dest)` reuses an existing file; pass `force=True` to re-download (was: always overwrote). It writes to a temp file and renames it, so a failed download leaves no truncated file.
- Server wire model: `PtmEntry` gains `accession` and `references` (DR lines as `{type, accession, value}`, the psimodpy/unimodpy shape); `PtmSummary` gains `accession`. `/api/health` is a typed `HealthResponse`; dashboard rows are `DashboardRow` TypedDicts.
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
- Tests recompute every entry's MM and MA from its correction formula against a frozen NIST table (pyteomics 5.0.1; generator in `tests/reference/`), plus Hypothesis property tests for the lookups. Upstream data errors found: PTM-0745 to PTM-0773 have MM and MA swapped (fixed upstream in 2026_03), PTM-0681's MM does not match its CF, PTM-0741's MM is truncated, PTM-0676 has a CF but no masses.

### Fixed

- `db.get_by_id(450)` raised `AttributeError`; it now returns PTM-0450. `db[key]` raises `KeyError` for any key that is not an int or str.
- `PtmDatabase` has `__contains__`: `key in db` accepts the same keys as `db[key]` (`PTM-0450`, bare `0450`, any case, or a name) and returns `False` for anything else instead of scanning entries. `entry in db` still works for entries.
- The MCP `search` tool rejects an empty `query`, like the REST `/api/search` endpoint; it used to return the first `limit` entries.
- `PtmDatabase.search(None)` (or any non-str query) returns `[]` instead of raising `AttributeError`, as in psimodpy and unimodpy.
- An entry with an unparseable `CF` no longer makes `dict_composition`/`proforma_formula` raise, so the server's `to_ptm_entry` (REST/MCP) cannot crash on it; both are `None`.

### Changed

- Bundled data refreshed to UniProt release 2026_03 (750 entries, was 748 from 2026_01): adds PTM-0775 (3'-chlorotyrosine) and PTM-0776 (cholesterol aspartate ester); upstream fixed the swapped MM/MA of PTM-0745 to PTM-0773 and updated PTM-0682 (TR, ChEBI). `data/ptmlist.tsv` regenerated with `write_tsv`.

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
