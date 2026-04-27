# uniprotptmpy

[![CI](https://github.com/tacular-omics/uniprotptmpy/actions/workflows/ci.yml/badge.svg)](https://github.com/tacular-omics/uniprotptmpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![Python](https://img.shields.io/pypi/pyversions/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Python library for parsing and querying the [UniProt post-translational modification (PTM) controlled vocabulary](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt).

- Zero core dependencies
- Bundled PTM data (748 entries) — works offline out of the box
- Typed, immutable data models (`py.typed` / PEP 561)
- TSV/CSV export and round-trip `ptmlist.txt` writer
- Optional FastAPI / [Model Context Protocol](https://modelcontextprotocol.io) server (`pip install uniprotptmpy[server]`)

## Online Viewer
#### [Click Me!](https://tacular-omics.github.io/uniprotptmpy/)

The same database is also reachable as a hosted REST + MCP service — see
[HTTP API and MCP Server](#http-api-and-mcp-server) below.


## Installation

```bash
pip install uniprotptmpy
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add uniprotptmpy
```

Requires Python 3.12+. No third-party dependencies.

## Quick Start

```python
from uniprotptmpy import load

# Load the bundled PTM database
db = load()
print(len(db))  # 748

# Look up by accession
entry = db.get_by_id("PTM-0450")
print(entry.name)  # (2-aminosuccinimidyl)acetic acid (Asn-Gly)

# Look up by name (case-insensitive)
entry = db.get_by_name("phosphoserine")
print(entry.id)  # PTM-0253

# Free-text search across name, ID, target, and keywords
results = db.search("acetylation")

# Dict-style access (raises KeyError if not found)
entry = db["PTM-0450"]

# Iterate all entries
for entry in db:
    print(entry.id, entry.name)
```

### Chemical Formulas

```python
entry = db.get_by_id("PTM-0476")  # 3-hydroxyproline
print(entry.correction_formula)   # O1
print(entry.dict_composition)     # {'O': 1}
print(entry.proforma_formula)     # O
```

### Exporting to TSV/CSV

```python
# Write all entries to a tab-separated file
db.write_tsv("ptms.tsv")

# Or CSV
db.write_tsv("ptms.csv", delimiter=",")

# Standalone function also available
from uniprotptmpy import write_tsv
write_tsv(db, "ptms.tsv")
```

### Writing back to ptmlist.txt format

```python
# Round-trip: write entries back to the original UniProt flat-file format
db.write_ptmlist("out/ptmlist.txt")

# Re-parse the written file — identical entry count and field values
from uniprotptmpy import parse_ptm_list
db2 = parse_ptm_list("out/ptmlist.txt")

# Standalone function
from uniprotptmpy import write_ptmlist
write_ptmlist(db, "out/ptmlist.txt")
```

### Downloading the Latest Data

```python
from uniprotptmpy import download, load

path = download()   # downloads to ~/.cache/uniprotptmpy/ptmlist.txt
db = load(path)     # load from the downloaded file
```

## HTTP API and MCP Server

The optional `[server]` extra ships a FastAPI app that exposes the same
database over a JSON REST API *and* over the
[Model Context Protocol](https://modelcontextprotocol.io) so language-model
tools can query the UniProt PTM vocabulary directly.

```bash
pip install uniprotptmpy[server]
uvicorn uniprotptmpy.server.app:app --reload
```

### REST endpoints

| Method & path | Returns |
|---------------|---------|
| `GET /api/health` | Service metadata and entry count. |
| `GET /api/entries?limit=&offset=` | Paginated full entries. |
| `GET /api/entries/{id}` | One full entry by accession (`PTM-0450` or `0450`). |
| `GET /api/entries/by-name/{name}` | One full entry by exact name. |
| `GET /api/search?q=&limit=` | Search hits as lightweight summaries. |

Search responses contain just `{id, name, feature_type, target,
monoisotopic_mass}` to keep token cost low; call `/api/entries/{id}` on any
hit for the full record (including taxonomic ranges and cross-references).

### MCP server

The same FastAPI app mounts an MCP endpoint at `POST /mcp` with three tools:

| Tool | Purpose |
|------|---------|
| `get_by_id(id)` | Look up a single PTM by accession. |
| `get_by_name(name)` | Exact name lookup. |
| `search(query, limit=25)` | Free-text search returning summaries. |

Tool responses use MCP's structured-output mechanism: the server emits an
`outputSchema` per tool in `tools/list` and returns both `structuredContent`
(typed Pydantic instance) and `content` (text fallback) on `tools/call`, so
LLM clients can parse the response without re-reading the JSON string.

Configure your MCP-aware client to point at `http://localhost:8000/mcp`
(or wherever you deploy the app). Example with the Anthropic CLI:

```bash
claude mcp add uniprot-ptm http://localhost:8000/mcp --transport http
```

## API Overview

| Symbol | Description |
|--------|-------------|
| `load(source=None)` | Load the PTM database. Uses bundled data by default. |
| `download(dest=None)` | Download the latest ptmlist.txt from UniProt FTP. |
| `parse_ptm_list(path)` | Parse a ptmlist.txt file into a `PtmDatabase`. |
| `write_tsv(entries, path, *, delimiter)` | Write entries to a TSV (or CSV) file. |
| `write_ptmlist(entries, path)` | Write entries back to UniProt ptmlist.txt flat-file format. |
| `PtmDatabase` | Indexed collection with `get_by_id()`, `get_by_name()`, `search()`, `write_tsv()`, `write_ptmlist()`, iteration, and `len()`. |
| `PtmEntry` | Frozen dataclass with all PTM fields, plus `dict_composition` and `proforma_formula` properties. |
| `FeatureType` | StrEnum: `CROSSLNK`, `MOD_RES`, `LIPID`, `CARBOHYD`, `DISULFID`. |
| `CrossReference` | Frozen dataclass with `database` and `accession` fields. |
| `TaxonomicRange` | Frozen dataclass with `taxon_name`, `tax_id`, `description`, and `raw` fields. |

## Development

```bash
just install   # install dependencies with uv
just lint      # ruff check
just format    # ruff format
just ty        # ty type check
just test      # pytest
just check     # lint + type check + test
```

## Related Projects

| Package | Description |
|---------|-------------|
| [unimodpy](https://github.com/tacular-omics/unimodpy) | Parse and query the UNIMOD mass spectrometry modifications database |
| [psimodpy](https://github.com/tacular-omics/psimodpy) | Parse and query the PSI-MOD protein modification ontology |

## License

[MIT](LICENSE)
