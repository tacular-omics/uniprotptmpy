from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from uniprotptmpy._download import PTM_LIST_URL, download


def test_download_default_dest() -> None:
    from uniprotptmpy import _download

    assert _download._DEFAULT_DEST == Path.home() / ".cache" / "uniprotptmpy" / "ptmlist.txt"


@patch("uniprotptmpy._download.urllib.request.urlretrieve")
def test_download_uses_default_dest(mock_urlretrieve: object, tmp_path: Path) -> None:
    dest = tmp_path / "cache" / "ptmlist.txt"
    with patch("uniprotptmpy._download._DEFAULT_DEST", dest):
        assert download() == dest
    assert dest.exists()


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
    mock_urlretrieve.assert_called_once()  # type: ignore[union-attr]
    url, target = mock_urlretrieve.call_args.args  # type: ignore[union-attr]
    assert url == PTM_LIST_URL
    assert Path(target).parent == dest.parent  # written to a temp file next to dest, then renamed
