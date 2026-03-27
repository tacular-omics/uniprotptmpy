# uniprotptmpy

[![CI](https://github.com/pgarrett-scripps/uniprotptmpy/actions/workflows/ci.yml/badge.svg)](https://github.com/pgarrett-scripps/uniprotptmpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![Python](https://img.shields.io/pypi/pyversions/uniprotptmpy)](https://pypi.org/project/uniprotptmpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Python library for parsing and querying the [UniProt post-translational modification (PTM) controlled vocabulary](https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt).

- Zero dependencies
- Bundled PTM data (748 entries) -- works offline out of the box
- Typed, immutable data models (`py.typed` / PEP 561)

## Installation

```bash
pip install uniprotptmpy
```

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

### Downloading the Latest Data

```python
from uniprotptmpy import download, load

path = download()   # downloads to ~/.cache/uniprotptmpy/ptmlist.txt
db = load(path)     # load from the downloaded file
```

## API Overview

| Symbol | Description |
|--------|-------------|
| `load(source=None)` | Load the PTM database. Uses bundled data by default. |
| `download(dest=None)` | Download the latest ptmlist.txt from UniProt FTP. |
| `parse_ptm_list(path)` | Parse a ptmlist.txt file into a `PtmDatabase`. |
| `PtmDatabase` | Indexed collection with `get_by_id()`, `get_by_name()`, `search()`, iteration, and `len()`. |
| `PtmEntry` | Frozen dataclass with all PTM fields, plus `dict_composition` and `proforma_formula` properties. |
| `FeatureType` | StrEnum: `CROSSLNK`, `MOD_RES`, `LIPID`, `CARBOHYD`, `DISULFID`. |
| `CrossReference` | Frozen dataclass with `database` and `accession` fields. |
| `TaxonomicRange` | Frozen dataclass with `taxon_name`, `tax_id`, `description`, and `raw` fields. |

## Development

```bash
just install   # install dependencies with uv
just lint      # ruff check
just format    # ruff format
just test      # pytest
just check     # lint + type check + test
```

## License

[MIT](LICENSE)
