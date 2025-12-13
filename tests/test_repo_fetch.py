import sys
import types
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ================================================================
# 1. PRE-INJECT FAKE scoring MODULE BEFORE IMPORTING repo_fetch
# ================================================================
fake_scoring = types.ModuleType("scoring")

# Minimal fake version of _hf_model_id_from_url
fake_scoring._hf_model_id_from_url = lambda url: "owner/repo"

sys.modules["scoring"] = fake_scoring

# ================================================================
# Now safe to import repo_fetch
# ================================================================
from backend.Rate.repo_fetch import (
    download_hf_repo_subset,
    read_text_if_exists,
)


# ================================================================
# TESTS
# ================================================================

def test_download_creates_directory(tmp_path, monkeypatch):
    """Ensures a directory is created and candidates are attempted."""
    
    # Mock requests.get to simulate successful fetch
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "FILE CONTENT"

    monkeypatch.setattr("backend.Rate.repo_fetch.requests.get", lambda *a, **kw: mock_resp)

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")
    assert outdir.exists()
    assert any(outdir.iterdir())  # At least 1 file should be created


def test_download_handles_http_failures(monkeypatch):
    """If requests.get fails, function must still return a directory without raising."""
    monkeypatch.setattr(
        "backend.Rate.repo_fetch.requests.get",
        lambda *a, **kw: MagicMock(status_code=404, text="")
    )

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")
    assert outdir.exists()
    # Should be empty because all requests failed
    assert len(list(outdir.iterdir())) == 0


def test_read_text_if_exists_reads_file(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("hello world")
    assert read_text_if_exists(tmp_path, "README.md") == "hello world"


def test_read_text_if_exists_missing_file(tmp_path):
    assert read_text_if_exists(tmp_path, "NOFILE.md") == ""


def test_read_text_if_exists_with_read_error(tmp_path, monkeypatch):
    p = tmp_path / "BAD.txt"
    p.write_text("data")

    def bad_read(*a, **kw):
        raise IOError("bad read")

    monkeypatch.setattr(Path, "read_text", bad_read)

    assert read_text_if_exists(tmp_path, "BAD.txt") == ""


def test_download_catches_request_exception(monkeypatch):
    """Force requests.get to raise an exception so repo_fetch hits the except block."""

    def bad_get(*args, **kwargs):
        raise RuntimeError("Network exploded")

    monkeypatch.setattr("backend.Rate.repo_fetch.requests.get", bad_get)

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")

    # Directory should still be created even though every request raised errors
    assert outdir.exists()
    # No files should be created
    assert len(list(outdir.iterdir())) == 0
