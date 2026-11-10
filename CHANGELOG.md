# Changelog

## [Unreleased]

### Documentation

- Add `db.get()` and membership checks to the README example and API table.

## [1.2.0] (2026-11-06)

### Fixed

- `search_mass`: passing `position` could *add* hits instead of removing them. A terminus
  slot (`sites` containing `"N-term"`/`"C-term"`, meaning the terminus itself, any residue)
  matched a residue query only when `position` named that terminus, so `position=None` -
  the least-constrained query - was the narrowest one. `position=None` now leaves both
  termini open and `position="anywhere"` closes both, which makes adding `position` only
  ever remove matches. **No behaviour change for this package's bundled data:** UniProt
  states the residue in `TG` and the polypeptide position in `PP`, so a terminus only ever
  reaches a slot's `where`, never its `sites`, and the corrected clause never fires. 0 of
  917 slots in the 2026_03 release carry a terminus name; 0 of 1200 swept queries widened
  before the fix and 0 of 3240 query result sets changed across it. `tests/test_position_narrows.py`
  is the guard that keeps it a no-op, and unit-tests the clause directly because the bundled
  data cannot reach it. Found by unimodpy, where the same `_mass.py` does change behaviour;
  psimodpy, unimodpy and uniprotptmpy apply the same bytes.

- `write_tsv`: multi-valued cells are separated by `" | "` instead of `"; "`, which could
  not be split back into values because the values contain `"; "` themselves. UniProt
  writes a taxonomic range as `Archaea; taxId:2157 (Archaea)`, so on the bundled 2026_03
  release all 1021 range values contain the old separator, and so do 54 of the 558 keyword
  values. Splitting the emitted cell on `"; "` therefore recovered the wrong number of
  values for **every one** of the 737 non-empty `taxonomic_ranges` cells, and for 54 of the
  557 non-empty `keywords` cells. No
  value in the release contains `"|"`. **This changes the output of `write_tsv` and the
  bundled `data/ptmlist.tsv`**, which has been regenerated: 198 of its 750 rows change,
  and only in those two columns. Consumers splitting on `"; "` must change to `" | "`.
  psimodpy uses the same separator for the same reason.

- `server` extra: `uvicorn>=0.30` could not be installed on any platform but emscripten.
  mcp requires `uvicorn>=0.31.1; sys_platform != "emscripten"`, so off emscripten no
  resolution of the extra contained a 0.30.x, and `--resolution lowest-direct` silently
  stepped over the declared floor - there the floor was unreachable rather than merely
  untested. Now `uvicorn>=0.31.1`. Off emscripten the raise states what mcp already
  required, so no environment that could install the extra before is excluded now. On
  emscripten mcp's requirement does not apply and this floor is the only bound, so a
  0.30.x was installable there and is not now.

### Changed

- **Data format:** `write_tsv` separates multi-valued cells with `" | "` instead of `"; "`,
  and the bundled `data/ptmlist.tsv` has been regenerated, so 198 of its 750 rows change in
  the `taxonomic_ranges` and `keywords` columns. This is listed under Fixed as well, because
  the old separator could not be split back; it is listed here because the bytes of a file
  shipped on PyPI change and a reader should not have to infer that from a Fixed bullet. Not
  breaking: no consumer splitting those columns on `"; "` could have been getting correct
  values, since 1021 of 1021 range values and 54 of 558 keyword values contain `"; "`
  themselves. Consumers must split on `" | "`. `peff_uniprot_fetcher` and `peff_digest` are
  downstream and worth checking.
- Tests only, no behaviour change: the two guards above name their columns by hand, so a
  third multi-valued column would be exported unchecked and nothing would say so. Two
  assertions close that: the set of tuple-typed `PtmEntry` fields must equal the joined set
  (`keywords`, `taxonomic_ranges`) plus the deliberately exempt one (`cross_references`,
  one `xref_<database>` column each), and no column outside the joined set may carry `" | "`
  in a real export. Adding a fourth tuple field fails the first; joining a third cell fails
  the second. The second is a subset and not an equality on purpose: only 1 entry in the
  bundled release has more than one keyword, against 197 with more than one taxonomic
  range, so equality would fail on a release that left every entry one keyword, which is
  not a defect.
- Tests only, no behaviour change: the export's round-trip part counts are asserted against
  the parser's, column by column: 1021 taxonomic-range parts and 558 keyword parts in the
  bundled release. The committed-equals-fresh test above catches a stale artifact but not a
  future value that itself contains `" | "`, because both sides would shred it identically;
  this catches that, and is asserted against the parsed total rather than a number written
  down here so a UniProt update moves both sides. Under the old `"; "` it reports
  `taxonomic_ranges: export yields 2042 parts, parser produced 1021`. Asked for by psimodpy,
  whose #65 asserts the same for synonyms.
- Tests only, no behaviour change: `data/ptmlist.tsv` is asserted to equal a fresh
  `write_tsv` of `data/ptmlist.txt`, byte for byte. That artifact is bundled, nothing reads
  it and no script regenerates it, which is exactly how it shipped with the wrong separator:
  nothing compared it to its source. A stale copy is now a test failure naming the first
  differing line, rather than a shipped defect. Reverting the file to its pre-fix state
  reports 198 of 750 rows differing; a single changed cell reports 1 of 750 at that line.
  Found and first measured by psimodpy, which exported a fresh TSV independently and matched
  the header and 750 of 750 rows.
- Tests only, no behaviour change: `write_tsv` keeps one `xref_<database>` column per
  database and builds it from a last-wins dict, so an entry carrying two cross-references
  in the same database would silently lose one. The bundled release has 1580
  cross-references and 1580 distinct (entry, database) pairs, so nothing is lost today;
  that is a fact about the data, not the code. A new test fails if a future release breaks
  it, instead of the export quietly dropping an accession. The column shape is unchanged.
- `server` extra: lowered the remaining floors to `fastapi>=0.110.1` (was `>=0.115`) and
  `mcp>=2.0.0,<3` (was `>=2.1.1,<3`). Both are reachable and tested: with `uvicorn`, `mcp`
  and `pydantic` pinned at their own floors, fastapi 0.110.1 installs and the whole server
  suite passes. `mcp>=2.0.0` is the lowest release under the `<3` cap, and lowering that
  floor does not unmask the old `uvicorn>=0.30`, because mcp 2.0.0 declares the same
  `uvicorn>=0.31.1; sys_platform != "emscripten"` that 2.1.1 did. 0.110.1 is a common floor
  shared with psimodpy and unimodpy rather than the lowest fastapi that works - 0.108.0 and
  0.100.0 resolve and pass the suite too. No change to what the package does.
- `server` extra: `pydantic>=2.12,<3`. The server has always imported pydantic at module
  level and never declared it. It only arrived transitively through fastapi and mcp. The
  floor excludes nothing installable, because every mcp release this extra allows
  requires `pydantic>=2.12.0`. The cap is now the only pydantic cap in a default install:
  fastapi carried `pydantic<3.0.0` up to 0.125.0 and declares a floor alone from 0.126.0
  on, and mcp declares a floor alone. pydantic has published no 3.x release, so the cap
  excludes nothing today either.

## [1.1.2] (2026-10-26)

### Changed

- The test suite now checks every bundled entry instead of a sample.
- `opentelemetry-api` moves to 1.45.1 in the locked environment (reached only
  through the optional `server` extra). GHSA: unbounded tracestate parsing.
- Updated development and test dependencies. No changes to the library.

## [1.1.1] (2026-09-25)

### Added

- Browser site (`docs/index.html`): mass search. Enter a signed delta mass, a tolerance in Da or ppm (ppm is relative to a precursor mass you enter) and monoisotopic or average mass. It combines with the text search, adds a sortable Δ error column (closest first) and keeps its state in the URL (`?mass=42.0106&tol=0.01&unit=da`). Same matching rule as `search_mass()`. `scripts/test_mass_search.py` checks it headless against `search_mass()` (needs Playwright).

### Changed

- Browser site restyled to the shared tacular-omics style (plain academic layout, labelled units, light and dark themes). The footer shows the package version the data came from.
- The source distribution now contains only the source, tests and the README, changelog, citation and license files: no paper, docs, lockfile or repository tooling.

## [1.1.0] (2026-09-24)

Additive only: nothing that worked in 1.0 changes behaviour.

### Added

- `load(cache=True)`: parse the bundled ptmlist.txt once per process and return that same database on later `load(cache=True)` calls. The database is shared by every such caller: do not modify it. Combining `cache=True` with `source` or `refresh=True` raises `ValueError`. The default (`cache=False`) still parses anew on each call.
- `UniprotPtmKeyError(UniprotPtmError, KeyError)`, exported: `db[key]` raises it on a miss. It is still a `KeyError`, not a `ValueError` (so `except KeyError` and `db.get` work as before) and `args[0]` is still the key.
- `search_mass(delta, *, tolerance=0.01, tolerance_unit="da", site=None, position=None) -> list[tuple[entry, float]]`: entries whose `monoisotopic_mass` (mass difference) is within `tolerance` of `delta`, as `(entry, error)` pairs with `error = delta - mass`, closest first (ties in mass, then file order). `tolerance_unit` accepts only `"da"` (exact, lowercase): ppm is not offered because a ppm window on a delta mass is ill-defined, and the keyword keeps the call shape of `tacular.tolerance` so units can be added later. Both window edges are inclusive. Entries without a mass are skipped. `site` is one or more residue letters (`"S"`, `"STY"`, any case; any of them matches, while `get_by_site` takes exactly one) or `"N-term"`/`"C-term"`, matched against the target residue(s) (`target`; crosslinks list each residue, "Asparagine or Aspartate" is N and D, "Undefined" matches no residue). `position` is where the residue was observed: `"anywhere"`, `"peptide n-term"`, `"peptide c-term"`, `"protein n-term"`, `"protein c-term"` (case-insensitive; `"Any N-term"`/`"Any C-term"` are aliases for the peptide ones). It is matched against the polypeptide position (`position`: Anywhere, N-terminal, C-terminal, with or without Protein core). UniProt does not distinguish protein from peptide terminus for these, so an N-terminal PTM matches both `"peptide n-term"` and `"protein n-term"`. Entries with no usable position count as anywhere. A modification of the terminus itself matches any residue at that terminus. A sorted mass index is built on the first call, and each search is a bisect. A bad `site`, `position`, `tolerance_unit`, `delta` or `tolerance` raises `UniprotPtmError`.
- `get_by_site(site)`: entries whose target includes residue `site` (one letter, case-insensitive), in file order. It takes exactly one residue (`search_mass(site=)` takes several). Unknown or non-string input returns `[]`.
- `PtmEntry.get_mass(*, monoisotopic=True) -> float | None`: the mass difference in Da, `monoisotopic_mass` (default) or `average_mass` (`monoisotopic=False`), with the same keyword as tacular 2.0's `get_mass`. The old attributes stay. `search_mass` uses it. It is only UniProt's own mass (`MM`/`MA`), or `None`: it never fills a missing mass from a linked PSI-MOD or Unimod entry, with or without the `link` extra, so `search_mass` gives the same results either way. For a linked mass, call `resolve()` and pick the entry yourself. It is not automatic because links do not always carry the same mass (PTM-0133, glycine radical, links to a PSI-MOD term with mass difference 0.0; some links are wrong; GPI-anchor links give only the core).
- `PtmEntry.psimod_ids` / `PtmEntry.unimod_ids`: linked accessions from `cross_references`, normalized to `"MOD:00046"` / `"UNIMOD:21"` (each accepts only its own prefix or bare digits, so a stray `"UNIMOD:46"` under PSI-MOD is ignored), in order and without duplicates (512 entries link to PSI-MOD, 252 to Unimod). They need no extra dependency.
- `PtmEntry.resolve("psimod" | "unimod")` returns the linked `psimodpy.PsiModEntry` / `unimodpy.UnimodEntry` objects from each package's bundled data, loaded once per process. It skips ids the linked release lacks. It needs the new optional extra `uniprotptmpy[link]` (`psimodpy>=1.1,<2`, `unimodpy>=1.1,<2`). Without the extra it raises `UniprotPtmError` saying to install it, and another target also raises `UniprotPtmError`.

### Changed

- `search()` is several times faster: each entry's lowercased name, id, target and keywords are joined once when the database is built, so a query is one substring test per entry instead of lowercasing every field on every call. Results and their order are unchanged (tested against the 1.0 algorithm).
- `import uniprotptmpy` no longer imports `urllib.request` (and with it `http.client`, `ssl`, `email`): it is imported when `download()` runs, saving about 30 ms at import.

## [1.0.0] (2026-09-23)

First stable release: the public API is now stable and follows semantic versioning.

Shared 1.0 API with psimodpy and unimodpy.

### Breaking

- `PtmEntry.proforma_formula` has no spaces: `"HO3P"`, `"H-3N-1"` (was `"H O3 P"`, `"H-3 N-1"`; 487 of 748 entries). Isotopes are bracketed (`"[13C6]"`). The bundled `data/ptmlist.tsv` and `write_tsv` output change with it.
- `PtmDatabase.get_by_id(ac)` parameter renamed to `id`. `get_by_id(ac=...)` still works with a `DeprecationWarning`.
- `get_by_id(True)` / `db[True]` / `True in db` no longer resolve to PTM-0001: `bool` is not an id (`None`, `KeyError`, `False`).
- `PtmDatabase(...)` raises `UniprotPtmError` on a duplicate accession (was: last one silently won). On a duplicate name the first entry keeps the name (was: last).
- Parser errors are typed: a non-numeric MM/MA, an `ID` inside an open block or a block with no closing `//` raise `UniprotPtmParseError` (a `ValueError`) with the file line. A duplicate accession raises `UniprotPtmError` with the line. A block missing AC, FT or TG was a bare `KeyError`. It is now skipped with a `UserWarning`, as is a block with an empty name.
- An unknown feature type (`FT`) no longer aborts the load with `ValueError`: the entry keeps the raw string in `feature_type` (typed `FeatureType | str`) and a warning is issued. An unparseable `CF` is kept raw with a warning. `dict_composition` and `proforma_formula` are `None` for it (they used to silently skip unknown tokens).
- `download(dest)` reuses an existing file. Pass `force=True` to re-download (was: always overwrote). It writes to a temp file and renames it, so a failed download leaves no truncated file.
- Server wire model: `PtmEntry` gains `accession` and `references` (DR lines as `{type, accession, value}`, the psimodpy/unimodpy shape). `PtmSummary` gains `accession`. `/api/health` is a typed `HealthResponse`. Dashboard rows are `DashboardRow` TypedDicts.
- Classifier `Development Status :: 5 - Production/Stable`.

Migration: replace `get_by_id(ac=x)` with `get_by_id(x)`. Code that split `proforma_formula` on spaces should use `dict_composition`. Catch `UniprotPtmParseError` (or `ValueError`) around `parse_ptm_list`/`load(path)`. Handle `feature_type` possibly being a plain `str` (`str(e.feature_type)` works for both). Call `download(force=True)` or `load(refresh=True)` to refresh the cache.

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

- `db.get_by_id(450)` raised `AttributeError`. It now returns PTM-0450. `db[key]` raises `KeyError` for any key that is not an int or str.
- `PtmDatabase` has `__contains__`: `key in db` accepts the same keys as `db[key]` (`PTM-0450`, bare `0450`, any case, or a name) and returns `False` for anything else instead of scanning entries. `entry in db` still works for entries.
- The MCP `search` tool rejects an empty `query`, like the REST `/api/search` endpoint. It used to return the first `limit` entries.
- `PtmDatabase.search(None)` (or any non-str query) returns `[]` instead of raising `AttributeError`, as in psimodpy and unimodpy.
- An entry with an unparseable `CF` no longer makes `dict_composition`/`proforma_formula` raise, so the server's `to_ptm_entry` (REST/MCP) cannot crash on it. Both are `None`.

### Changed

- Bundled data refreshed to UniProt release 2026_03 (750 entries, was 748 from 2026_01): adds PTM-0775 (3'-chlorotyrosine) and PTM-0776 (cholesterol aspartate ester). Upstream fixed the swapped MM/MA of PTM-0745 to PTM-0773 and updated PTM-0682 (TR, ChEBI). `data/ptmlist.tsv` regenerated with `write_tsv`.

## [0.2.2] (2026-09-23)

### Fixed

- The MCP `search` tool rejects a `limit` outside 1-500, like the REST `/api/search` endpoint. `-1` used to return nearly every entry.
- The server parses the bundled `ptmlist.txt` once at import instead of twice (the dashboard payload reuses the loaded database). `dashboard_entries()` takes an optional `db`.
- `just lint` and `just format` cover `tests` as well as `src`, matching CI.
- Removed the unused `requirements.txt`. Vercel installs the `server` extra via `installCommand` in `vercel.json`.

## [0.2.1] (2026-09-23)

### Added

- Releases are archived on Zenodo (`.zenodo.json`). No code changes.

## [0.2.0] (2026-09-23)

### Added

- `write_ptmlist` writes entries back to the `ptmlist.txt` format.
- TSV/CSV writer for PTM entries. `cross_references` is split into one column per database.
- Online UniProt PTM browser (GitHub Pages) with search, sort, filter and a full detail view.
- FastAPI REST API and MCP server (`server` extra), deployable to Vercel, which also serves the browser dashboard at the root.

### Changed

- **Breaking for the `server` extra:** the MCP server was ported from FastMCP (mcp 1.x) to `MCPServer` (mcp 2.x). It now requires mcp 2.
- MCP tools return typed responses (`structuredContent` with an `outputSchema`).
- Releases publish to PyPI by trusted publishing. The version lives only in `uniprotptmpy.__version__`, with `CITATION.cff` kept in sync.

### Fixed

- The dashboard HTML is read as UTF-8, so it loads on Windows.
- The MCP session manager is created per request, fixing session reuse errors on Vercel.

## [0.1.2] (2026-03-27)

- Packaging and build fixes.

## [0.1.1] (2026-03-27)

- Packaging fixes. Development dependencies moved to dependency groups.

## [0.1.0] (2026-03-26)

* First release on PyPI.
