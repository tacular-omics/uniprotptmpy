# uniprotptmpy

[![CI](https://github.com/tacular-omics/uniprotptmpy/actions/workflows/ci.yml/badge.svg)](https://github.com/tacular-omics/uniprotptmpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![Python](https://img.shields.io/pypi/pyversions/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22926364.svg)](https://doi.org/10.5281/zenodo.22926364)

uniprotptmpy wraps the [UniProt post-translational modification (PTM)
controlled vocabulary](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt)
in a typed Python API, so proteomics tooling can look up PTMs by accession,
name, or free text without writing a parser for UniProt's `ptmlist.txt` flat
file. It ships with the full vocabulary bundled in, so it works fully
offline.

## Highlights

- **Bundled, offline data** — 748 PTM entries shipped with the package; no network calls needed
- **Zero core dependencies** — pure Python, `pip install` and go
- **Typed, immutable models** with `py.typed` (PEP 561) for IDE autocomplete and static checking
- **Rich lookups** — by accession (`PTM-0450`), exact name, free-text search across name/target/keywords, subscript access, and iteration
- **Formula helpers** computed for you (elemental composition dicts, ProForma-style formula strings)
- **Round-trip export** to TSV/CSV and back to the original `ptmlist.txt` format
- **[Online browser](https://tacular-omics.github.io/uniprotptmpy/)** — search, sort, and inspect every term, no install required
- **Optional local FastAPI + [MCP](https://modelcontextprotocol.io) server** (`pip install uniprotptmpy[server]`) to expose the database over HTTP or to LLM tools

## Install

```bash
pip install uniprotptmpy
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add uniprotptmpy
```

Requires Python 3.12+. No third-party dependencies for the core package.

## Quick Example

```python
from uniprotptmpy import load

db = load()                   # bundled PTM database, no download needed
print(len(db))                # 748

# Lookup by accession
entry = db.get_by_id("PTM-0450")
print(entry.name)             # (2-aminosuccinimidyl)acetic acid (Asn-Gly)

# Lookup by exact name (case-insensitive)
entry = db.get_by_name("phosphoserine")
print(entry.id)               # PTM-0253

# Free-text search across name, ID, target, and keywords
results = db.search("acetylation")
print(len(results))           # 17

# Dict-style access, iteration, and formula helpers
entry = db["PTM-0450"]
hydroxy = db.get_by_id("PTM-0476")
print(hydroxy.correction_formula)  # O1
print(hydroxy.dict_composition)    # {'O': 1}
print(hydroxy.proforma_formula)    # O
```

## More

<details>
<summary>Downloading the latest data, TSV/CSV export, ptmlist.txt round-trip</summary>

```python
from uniprotptmpy import download, load, write_tsv, write_ptmlist, parse_ptm_list

# Download the latest list from UniProt's FTP site
path = download()   # ~/.cache/uniprotptmpy/ptmlist.txt
db = load(path)

# Write every entry to TSV (or CSV)
db.write_tsv("ptms.tsv")
db.write_tsv("ptms.csv", delimiter=",")

# Round-trip back to the original UniProt flat-file format
db.write_ptmlist("out/ptmlist.txt")
db2 = parse_ptm_list("out/ptmlist.txt")  # identical entry count and fields
```

</details>

<details>
<summary>Local HTTP API and MCP server (<code>pip install uniprotptmpy[server]</code>)</summary>

```bash
pip install uniprotptmpy[server]
uvicorn uniprotptmpy.server.app:app --reload
```

This starts a FastAPI app exposing the database as both a JSON REST API
(`GET /api/entries/{id}`, `/api/search`, `/api/entries/by-name/{name}`, …)
and an [MCP](https://modelcontextprotocol.io) endpoint at `POST /mcp` with
`get_by_id`, `get_by_name`, and `search` tools, for pointing LLM clients
directly at the UniProt PTM vocabulary:

```bash
claude mcp add uniprot-ptm http://localhost:8000/mcp --transport http
```

</details>

<details>
<summary>Full API reference</summary>

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

</details>

See [`CHANGELOG.md`](https://github.com/tacular-omics/uniprotptmpy/blob/main/CHANGELOG.md)
for release history.

## Data Source

Term data comes from [UniProt's PTM controlled vocabulary list](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt),
maintained by the UniProt Consortium. See uniprot.org for the vocabulary's
own license and citation guidance.

## Related Projects

Part of the `tacular-omics` family of proteomics PTM-vocabulary packages:

| Package | Description |
|---------|-------------|
| [unimodpy](https://github.com/tacular-omics/unimodpy) | Parse and query the UNIMOD mass spectrometry modifications database |
| [psimodpy](https://github.com/tacular-omics/psimodpy) | Parse and query the PSI-MOD protein modification ontology |
| [tacular](https://github.com/tacular-omics/tacular) | Broader MS-proteomics lookup library (amino acids, elements, fragment-ion masses) that bundles its own copies of UniProt-PTM alongside UNIMOD, PSI-MOD, RESID, XLMOD, and GNOme; the base library for peptacular and paftacular |

## Citation

If uniprotptmpy is useful in your research, please cite it — see
[`CITATION.cff`](https://github.com/tacular-omics/uniprotptmpy/blob/main/CITATION.cff)
or use the "Cite this repository" button on GitHub. Releases are archived on
Zenodo (DOI badge above).

## License

[MIT](LICENSE)
