# tests/test_repo_fetch.py

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# ================================================================
# 1. PRE-INJECT fake scoring BEFORE importing repo_fetch
# ================================================================
_fake_scoring = types.ModuleType("scoring")
_fake_scoring._hf_model_id_from_url = lambda url: "owner/repo"
sys.modules["scoring"] = _fake_scoring

# ================================================================
# 2. NOW safe to import repo_fetch
# ================================================================
from backend.Rate.repo_fetch import (
    download_hf_repo_subset,
    read_text_if_exists,
)

# ================================================================
# 3. CLEANUP after file import so other tests are unaffected
# ================================================================
def teardown_module(module):
    sys.modules.pop("scoring", None)


# ================================================================
# TESTS
# ================================================================

def test_download_creates_directory(tmp_path, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "FILE CONTENT"

    monkeypatch.setattr(
        "backend.Rate.repo_fetch.requests.get",
        lambda *a, **kw: mock_resp
    )

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")
    assert outdir.exists()
    assert any(outdir.iterdir())


def test_download_handles_http_failures(monkeypatch):
    monkeypatch.setattr(
        "backend.Rate.repo_fetch.requests.get",
        lambda *a, **kw: MagicMock(status_code=404, text="")
    )

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")
    assert outdir.exists()
    assert list(outdir.iterdir()) == []


def test_download_catches_request_exception(monkeypatch):
    def bad_get(*a, **kw):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(
        "backend.Rate.repo_fetch.requests.get",
        bad_get
    )

    outdir = download_hf_repo_subset("https://huggingface.co/owner/repo")
    assert outdir.exists()
    assert list(outdir.iterdir()) == []


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
