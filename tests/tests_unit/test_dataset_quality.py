"""Unit tests for the Dataset Quality metric.

Tests dataset quality scoring based on README content, trusted datasets,
and dataset quality indicators found in model documentation.
"""

from unittest.mock import MagicMock

from backend.Rate.metrics.dataset_quality import dataset_quality
from backend.Rate.metrics import dataset_quality as dq


def test_empty_readme_returns_zero(monkeypatch):
    """Empty README should return score of 0.0."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(dq, "fetch_hf_readme_text", lambda _: "")

    score, latency = dataset_quality("x", "y", "z")
    assert score == 0.0
    assert isinstance(latency, int)


def test_dataset_from_api_metadata(monkeypatch):
    """Dataset from API metadata with readme should score >= 0.6."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(dq, "fetch_hf_readme_text", lambda _: "some text")

    api_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "cardData": {"datasets": ["MNIST"]},
        },
    )
    monkeypatch.setattr(dq.requests, "get", lambda *a, **k: api_resp)

    score, _ = dataset_quality("x", "y", "z")
    assert score >= 0.6


def test_strong_trusted_datasets(monkeypatch):
    """Strong trusted datasets like BookCorpus and Wikipedia should score >= 0.9."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        dq,
        "fetch_hf_readme_text",
        lambda _: "Trained on BookCorpus and Wikipedia with filtering",
    )
    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert score >= 0.9


def test_multiple_trusted_datasets(monkeypatch):
    """Multiple trusted datasets like ImageNet and COCO should score between 0.8 and 0.95."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        dq,
        "fetch_hf_readme_text",
        lambda _: "Uses ImageNet and COCO datasets",
    )
    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert 0.8 <= score <= 0.95


def test_single_trusted_dataset(monkeypatch):
    """Single trusted dataset like CIFAR-10 should score between 0.6 and 0.9."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        dq,
        "fetch_hf_readme_text",
        lambda _: "trained on CIFAR-10 dataset",
    )
    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert 0.6 <= score <= 0.9


def test_dataset_section_detection(monkeypatch):
    """Dataset section header should be properly detected and scored."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        dq,
        "fetch_hf_readme_text",
        lambda _: """
        ## Dataset
        This model was trained on OpenWebText and C4.
        """,
    )
    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert score >= 0.8


def test_quality_keywords_boost_score(monkeypatch):
    """Quality keywords like cleaning, deduplication, and splits should boost score."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        dq,
        "fetch_hf_readme_text",
        lambda _: """
        Trained on Wikipedia.
        Data cleaning, deduplication, filtering applied.
        Train/val/test splits used.
        """,
    )
    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert score > 0.6

def test_api_failure_is_ignored(monkeypatch):
    """API failures should not prevent scoring from trusted dataset keywords."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(dq, "fetch_hf_readme_text", lambda _: "trained on mnist")

    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api down")),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert score >= 0.6

def test_no_dataset_signals(monkeypatch):
    """No dataset information should return score of 0.0."""
    monkeypatch.setattr(dq, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(dq, "fetch_hf_readme_text", lambda _: "just some text")

    monkeypatch.setattr(
        dq.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_quality("x", "y", "z")
    assert score == 0.0


