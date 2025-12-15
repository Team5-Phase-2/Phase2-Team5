"""Unit tests for the code_quality metric.

Tests the code_quality scoring function which evaluates Python code quality
in GitHub repositories. Verifies URL validation, API integration, and analysis logic.
"""

# tests/test_code_quality.py

import pytest
from unittest.mock import MagicMock
import time

from backend.Rate.metrics.code_quality import code_quality
from backend.Rate.metrics import code_quality as cq


def test_non_github_url_returns_default():
    """Verify that non-GitHub URLs return default score of 0.5."""
    score, latency = code_quality(
        model_url="x",
        code_url="https://example.com/notgithub",
        dataset_url=None,
    )
    assert score == 0.5
    assert isinstance(latency, int)


def test_github_api_failure_returns_default(monkeypatch):
    """Verify that GitHub API failures return default score of 0.5."""
    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo",
        dataset_url=None,
    )
    assert score == 0.5


def test_no_python_files_returns_default(monkeypatch):
    """Verify that repos with no Python files return default score of 0.5."""
    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda *a, **k: MagicMock(
            status_code=200,
            json=lambda: [{"type": "file", "name": "README.md"}],
        ),
    )

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo",
        dataset_url=None,
    )
    assert score == 0.5


def test_python_files_with_analysis(monkeypatch):
    """Verify that code analysis is performed on Python files."""
    contents_resp = MagicMock(
        status_code=200,
        json=lambda: [{"type": "file", "name": "a.py", "path": "a.py"}],
    )
    raw_resp = MagicMock(status_code=200, text="print('hi')")

    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda url, *a, **k: contents_resp if "api.github.com" in url else raw_resp,
    )
    monkeypatch.setattr(
        cq,
        "analyze_code",
        lambda *_: 0.8,
    )

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo",
        dataset_url=None,
    )
    assert score == pytest.approx(0.8)


def test_analyzer_exception_returns_fallback(monkeypatch):
    """Verify that code analyzer exceptions return default score of 0.5."""
    contents_resp = MagicMock(
        status_code=200,
        json=lambda: [{"type": "file", "name": "a.py", "path": "a.py"}],
    )
    raw_resp = MagicMock(status_code=200, text="bad")

    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda url, *a, **k: contents_resp if "api.github.com" in url else raw_resp,
    )
    monkeypatch.setattr(
        cq,
        "analyze_code",
        lambda *_: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo",
        dataset_url=None,
    )
    assert score == 0.5

def test_git_suffix_is_stripped(monkeypatch):
    """Verify that .git suffix is properly stripped from repository URLs."""
    contents_resp = MagicMock(
        status_code=200,
        json=lambda: [{"type": "file", "name": "a.py", "path": "a.py"}],
    )
    raw_resp = MagicMock(status_code=200, text="print('hi')")

    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda url, *a, **k: contents_resp if "api.github.com" in url else raw_resp,
    )
    monkeypatch.setattr(cq, "analyze_code", lambda *_: 0.7)

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo.git",
        dataset_url=None,
    )
    assert score == pytest.approx(0.7)


def test_missing_owner_or_repo_returns_default():
    """Verify that incomplete GitHub URLs return default score of 0.5."""
    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/",
        dataset_url=None,
    )
    assert score == 0.5

def test_python_file_limit_break(monkeypatch):
    """Verify that processing stops after limit of Python files is reached."""
    contents_resp = MagicMock(
        status_code=200,
        json=lambda: [
            {"type": "file", "name": f"{i}.py", "path": f"{i}.py"}
            for i in range(10)
        ],
    )
    raw_resp = MagicMock(status_code=200, text="print('hi')")

    monkeypatch.setattr(
        cq.requests,
        "get",
        lambda url, *a, **k: contents_resp if "api.github.com" in url else raw_resp,
    )
    monkeypatch.setattr(cq, "analyze_code", lambda *_: 0.6)

    score, _ = code_quality(
        model_url="x",
        code_url="https://github.com/owner/repo",
        dataset_url=None,
    )
    assert score == pytest.approx(0.6)


