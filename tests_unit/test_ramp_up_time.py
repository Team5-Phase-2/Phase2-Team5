"""Unit tests for the Ramp-Up Time metric.

Tests ease of getting started with a model based on documentation quality,
popularity indicators, metadata, and example code availability.
"""

# tests/test_ramp_up_time.py

import pytest
from unittest.mock import MagicMock

import backend.Rate.metrics.ramp_up_time as rut



def test_http_model_id_returns_none(monkeypatch):
    """Invalid HTTP model ID should return None score."""
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "http://bad")

    score, latency = rut.ramp_up_time("x", "y", "z")
    assert score is None
    assert isinstance(latency, int)


def test_api_non_200_returns_none(monkeypatch):
    """Non-200 API response should return None score."""
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        rut.requests,
        "get",
        lambda *a, **k: MagicMock(status_code=404),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score is None


def test_api_exception_returns_none(monkeypatch):
    """API request exception should return None score."""
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        rut.requests,
        "get",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score is None


def test_minimal_metadata_score(monkeypatch):
    """Minimal metadata with no documentation should return low score."""
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        rut.requests,
        "get",
        lambda *a, **k: MagicMock(
            status_code=200,
            json=lambda: {"likes": 0, "siblings": [], "cardData": None, "tags": []},
        ),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score == pytest.approx(0.18, rel=1e-2)  # 0.6 * 0.3


def test_likes_and_readme_score(monkeypatch):
    """Model with likes and README should score above 0.6."""
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        rut.requests,
        "get",
        lambda *a, **k: MagicMock(
            status_code=200,
            json=lambda: {
                "likes": 1000,
                "siblings": [{"rfilename": "README.md"}],
                "cardData": {},
                "tags": [],
            },
        ),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score > 0.6
    assert score <= 1.0

"""Tutorial and example tags should provide bonus to score."""
    
def test_examples_bonus_applied(monkeypatch):
    monkeypatch.setattr(rut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        rut.requests,
        "get",
        lambda *a, **k: MagicMock(
            status_code=200,
            json=lambda: {
                "likes": 10,
                "siblings": [{"rfilename": "README.md"}],
                "cardData": {},
                "tags": ["tutorial", "example"],
            },
        ),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score > 0.6  # includes bonus

"""Unexpected outer exception should return None score."""
    
def test_outer_exception_returns_none(monkeypatch):
    monkeypatch.setattr(
        rut,
        "_hf_model_id_from_url",
        lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    score, _ = rut.ramp_up_time("x", "y", "z")
    assert score is None
