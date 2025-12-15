"""Unit tests for the Performance Claims metric.

Tests whether model performance claims are documented in README or other
documentation files, including handling of download failures and missing files.
"""

import pytest
import backend.Rate.metrics.performance_claims as pc


def test_readme_has_text_returns_one(monkeypatch):
    """README with performance metrics should return score of 1.0."""
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(
        pc,
        "read_text_if_exists",
        lambda repo, name: "Accuracy: 95%" if name == "README.md" else "",
    )

    score, latency = pc.performance_claims("model", "code", "data")
    assert score == 1.0
    assert isinstance(latency, int)




def test_no_files_with_text_returns_point_one(monkeypatch):
    """No documentation files with performance claims should return score of 0.1."""
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(pc, "read_text_if_exists", lambda *_: "")

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.1


def test_download_exception_returns_zero(monkeypatch):
    """Repository download failure should return score of 0.0."""
    monkeypatch.setattr(
        pc,
        "download_hf_repo_subset",
        lambda _: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.0


def test_read_exception_returns_zero(monkeypatch):
    """File read failure should return score of 0.0."""
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(
        pc,
        "read_text_if_exists",
        lambda *_: (_ for _ in ()).throw(RuntimeError("read fail")),
    )

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.0
