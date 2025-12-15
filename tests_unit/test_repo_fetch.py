"""Unit tests for the Repository Fetch module.

Tests downloading Hugging Face repositories, handling HTTP failures,
and reading text files from downloaded repository directories.
"""

# tests/test_repo_fetch.py

import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(scope="module")
def repo_fetch_module():
    """
    Make sure 'scoring' resolves to the REAL backend.Rate.scoring module
    before importing repo_fetch, then restore sys.modules afterward.
    """
    old_scoring = sys.modules.get("scoring")

    # Alias "scoring" -> real module (NOT a fake!)
    real_scoring = importlib.import_module("backend.Rate.scoring")
    sys.modules["scoring"] = real_scoring

    # Now repo_fetch can import safely
    repo_fetch = importlib.import_module("backend.Rate.repo_fetch")

    yield repo_fetch

    # Restore previous state so other tests (like test_scoring.py) are not affected
    if old_scoring is None:
        sys.modules.pop("scoring", None)
    else:
        sys.modules["scoring"] = old_scoring

    # Also remove repo_fetch so it doesn't keep references across files/runs
    sys.modules.pop("backend.Rate.repo_fetch", None)


def test_download_creates_directory(repo_fetch_module, monkeypatch):
    """Successful download should create output directory with files."""
    mock_resp = MagicMock(status_code=200, text="FILE CONTENT")
    monkeypatch.setattr(repo_fetch_module.requests, "get", lambda *a, **kw: mock_resp)

    with patch("backend.Rate.repo_fetch._hf_model_id_from_url", return_value="owner/repo"):
        outdir = repo_fetch_module.download_hf_repo_subset("https://huggingface.co/owner/repo")

    assert outdir.exists()
    assert any(outdir.iterdir())


def test_download_handles_http_failures(repo_fetch_module, monkeypatch):
    """HTTP 404 response should result in empty directory."""
    monkeypatch.setattr(
        repo_fetch_module.requests,
        "get",
        lambda *a, **kw: MagicMock(status_code=404, text="")
    )

    with patch("backend.Rate.repo_fetch._hf_model_id_from_url", return_value="owner/repo"):
        outdir = repo_fetch_module.download_hf_repo_subset("https://huggingface.co/owner/repo")

    assert outdir.exists()
    assert list(outdir.iterdir()) == []


def test_download_catches_request_exception(repo_fetch_module, monkeypatch):
    """Request exception should be caught and result in empty directory."""
    def bad_get(*a, **kw):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(repo_fetch_module.requests, "get", bad_get)

    with patch("backend.Rate.repo_fetch._hf_model_id_from_url", return_value="owner/repo"):
        outdir = repo_fetch_module.download_hf_repo_subset("https://huggingface.co/owner/repo")

    assert outdir.exists()
    assert list(outdir.iterdir()) == []


def test_read_text_if_exists_reads_file(repo_fetch_module, tmp_path):
    """File that exists should be read and returned as string."""
    p = tmp_path / "README.md"
    p.write_text("hello world")
    assert repo_fetch_module.read_text_if_exists(tmp_path, "README.md") == "hello world"


def test_read_text_if_exists_missing_file(repo_fetch_module, tmp_path):
    """Missing file should return empty string."""
    assert repo_fetch_module.read_text_if_exists(tmp_path, "NOFILE.md") == ""


def test_read_text_if_exists_with_read_error(repo_fetch_module, tmp_path, monkeypatch):
    """Read error should be caught and empty string returned."""
    p = tmp_path / "BAD.txt"
    p.write_text("data")

    def bad_read(*a, **kw):
        raise IOError("bad read")

    monkeypatch.setattr(Path, "read_text", bad_read)
    assert repo_fetch_module.read_text_if_exists(tmp_path, "BAD.txt") == ""
