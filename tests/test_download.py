from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from uniprotptmpy._download import PTM_LIST_URL, download


@patch("uniprotptmpy._download.urllib.request.urlretrieve")
def test_download_default_dest(mock_urlretrieve: object) -> None:
    result = download()
    expected = Path.home() / ".cache" / "uniprotptmpy" / "ptmlist.txt"
    assert result == expected


@patch("uniprotptmpy._download.urllib.request.urlretrieve")
def test_download_custom_dest(mock_urlretrieve: object, tmp_path: Path) -> None:
    dest = tmp_path / "custom.txt"
    result = download(dest)
    assert result == dest


@patch("uniprotptmpy._download.urllib.request.urlretrieve")
def test_download_creates_parent_dirs(mock_urlretrieve: object, tmp_path: Path) -> None:
    dest = tmp_path / "a" / "b" / "ptmlist.txt"
    download(dest)
    assert dest.parent.exists()


@patch("uniprotptmpy._download.urllib.request.urlretrieve")
def test_download_calls_urlretrieve_with_correct_url(mock_urlretrieve: object, tmp_path: Path) -> None:
    dest = tmp_path / "ptmlist.txt"
    download(dest)
    mock_urlretrieve.assert_called_once_with(PTM_LIST_URL, dest)  # type: ignore[union-attr]
