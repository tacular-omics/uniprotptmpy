"""Download the latest ptmlist.txt from UniProt FTP."""

from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

PTM_LIST_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/docs/ptmlist.txt"
_DEFAULT_DEST = Path.home() / ".cache" / "uniprotptmpy" / "ptmlist.txt"


def download(dest: Path | str | None = None, *, force: bool = False) -> Path:
    """Download the latest ptmlist.txt from UniProt FTP and return its path.

    ``dest`` defaults to ``~/.cache/uniprotptmpy/ptmlist.txt``. An existing file is
    reused unless ``force=True``.
    """
    dest = Path(dest) if dest is not None else _DEFAULT_DEST
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Download next to dest, then rename: a failed download never leaves a truncated cache file.
    fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".part")
    os.close(fd)
    try:
        urllib.request.urlretrieve(PTM_LIST_URL, tmp_name)
        os.replace(tmp_name, dest)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
    return dest
