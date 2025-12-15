"""Unit tests for the Dataset and Code Score metric.

Tests code and dataset URL detection, Hugging Face model ID extraction,
and scoring logic for various combinations of present/missing resources.
"""

from unittest.mock import MagicMock

from backend.Rate.metrics.dataset_code import dataset_and_code_score
from backend.Rate.metrics import dataset_code as dc


def test_both_urls_present_short_circuit():
    """When both code and dataset URLs are present, return perfect score of 1.0."""
    score, latency = dataset_and_code_score(
        model_url="x",
        code_url="something",
        dataset_url="something",
    )
    assert score == 1.0
    assert isinstance(latency, int)


def test_http_model_id_returns_zero(monkeypatch):
    """Invalid HTTP model ID should return score of 0.0."""
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "http://bad",
    )

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.0


def test_code_only_returns_half(monkeypatch):
    """When only code URL is present, return score of 0.5."""
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )
    monkeypatch.setattr(
        dc.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="present",
        dataset_url="NULL",
    )
    assert score == 0.5


def test_dataset_only_returns_half(monkeypatch):
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )
    monkeypatch.setattr(
        dc.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="present",
    )
    assert score == 0.5


def test_dataset_from_card_metadata(monkeypatch):
    """When only dataset URL is present, return score of 0.5."""
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )

    api_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "cardData": {"datasets": ["imagenet"]},
            "siblings": [],
        },
    )

    monkeypatch.setattr(dc.requests, "get", lambda *a, **k: api_resp)

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.5


def test_code_from_sibling_py_file(monkeypatch):
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )

    api_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "cardData": {},
            "siblings": [{"rfilename": "example.py"}],
        },
    )

    monkeypatch.setattr(dc.requests, "get", lambda *a, **k: api_resp)

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.5


def test_code_from_readme_fallback(monkeypatch):
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )

    api_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "cardData": {},
            "siblings": [],
        },
    )

    monkeypatch.setattr(dc.requests, "get", lambda *a, **k: api_resp)
    monkeypatch.setattr(
        dc,
        "fetch_hf_readme_text",
        lambda _: "```python\nfrom transformers import AutoModel\n```",
    )

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.5


def test_neither_dataset_nor_code(monkeypatch):
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )

    api_resp = MagicMock(
        status_code=200,
        json=lambda: {
            "cardData": {},
            "siblings": [],
        },
    )

    monkeypatch.setattr(dc.requests, "get", lambda *a, **k: api_resp)
    monkeypatch.setattr(dc, "fetch_hf_readme_text", lambda _: "")

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.0


def test_api_failure_still_works(monkeypatch):
    monkeypatch.setattr(
        dc,
        "_hf_model_id_from_url",
        lambda _: "owner/repo",
    )
    monkeypatch.setattr(
        dc.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=500),
    )

    score, _ = dataset_and_code_score(
        model_url="x",
        code_url="NULL",
        dataset_url="NULL",
    )
    assert score == 0.0


