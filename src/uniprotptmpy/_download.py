from __future__ import annotations

import urllib.request
from pathlib import Path

PTM_LIST_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt"
_DEFAULT_DEST = Path.home() / ".cache" / "uniprotptmpy" / "ptmlist.txt"


def download(dest: Path | str | None = None) -> Path:
    """Download the latest ptmlist.txt from UniProt FTP."""
    dest = Path(dest) if dest is not None else _DEFAULT_DEST
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(PTM_LIST_URL, dest)
    return dest
