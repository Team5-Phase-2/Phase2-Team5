# tests/test_performance_claims.py

import pytest
import backend.Rate.metrics.performance_claims as pc


def test_readme_has_text_returns_one(monkeypatch):
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(
        pc,
        "read_text_if_exists",
        lambda repo, name: "Accuracy: 95%" if name == "README.md" else "",
    )

    score, latency = pc.performance_claims("model", "code", "data")
    assert score == 1.0
    assert isinstance(latency, int)


def test_model_index_has_text_returns_one(monkeypatch):
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(
        pc,
        "read_text_if_exists",
        lambda repo, name: '{"metrics": {"acc": 0.9}}' if name == "model_index.json" else "",
    )

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 1.0


def test_no_files_with_text_returns_point_one(monkeypatch):
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(pc, "read_text_if_exists", lambda *_: "")

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.1


def test_download_exception_returns_zero(monkeypatch):
    monkeypatch.setattr(
        pc,
        "download_hf_repo_subset",
        lambda _: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.0


def test_read_exception_returns_zero(monkeypatch):
    monkeypatch.setattr(pc, "download_hf_repo_subset", lambda _: "/tmp/repo")
    monkeypatch.setattr(
        pc,
        "read_text_if_exists",
        lambda *_: (_ for _ in ()).throw(RuntimeError("read fail")),
    )

    score, _ = pc.performance_claims("model", "code", "data")
    assert score == 0.0
