"""Unit tests for the Reproducibility metric.

Tests assessment of model reproducibility based on code examples in documentation
and GenAI evaluation of setup feasibility.
"""

# tests/test_reproducibility.py

import json
import importlib
import pytest


@pytest.fixture
def rp():
    """
    Always import reproducibility fresh.
    Avoid reload(); metric_runner tests corrupt sys.modules ordering.
    """
    return importlib.import_module("backend.Rate.metrics.reproducibility")


def _mock_genai_response(status_code: float):
    """Helper: Create mock GenAI response with status code."""
    return {
        "body": json.dumps({
            "choices": [
                {
                    "message": {
                        "content": f"Final Response -- Status Code : {status_code}"
                    }
                }
            ]
        })
    }


def test_reproducibility_returns_one(monkeypatch, rp):
    """Code example and successful GenAI evaluation should return score of 1.0."""
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "```python\nprint('hi')\n```")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(1))

    score, latency = rp.reproducibility("model", "code", "data")

    assert score == 1.0
    assert isinstance(latency, int)


def test_reproducibility_returns_half(monkeypatch, rp):
    """Partial GenAI evaluation should return score of 0.5."""
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0.5))

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.5


def test_reproducibility_returns_zero(monkeypatch, rp):
    """Failed GenAI evaluation should return score of 0.0."""
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0))

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.0


def test_query_genai_error_returns_zero(monkeypatch, rp):
    """GenAI query error should return score of 0.0."""
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: "Error")

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.0


def test_missing_status_code_returns_zero(monkeypatch, rp):
    """Missing status code in response should return score of 0.0."""
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(
        rp,
        "query_genai",
        lambda _: {
            "body": json.dumps({
                "choices": [
                    {"message": {"content": "No status code here"}}
                ]
            })
        },
    )

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.0


def test_extract_status_code_valid(rp):
    """Valid status codes should be extracted correctly."""
    assert rp.extract_status_code("Final Response -- Status Code : 1") == 1.0
    assert rp.extract_status_code("Final Response -- Status Code : 0.5") == 0.5
    assert rp.extract_status_code("Final Response -- Status Code : 0") == 0.0

"""Invalid or missing status codes should return 0.0."""
    
def test_extract_status_code_invalid(rp):
    assert rp.extract_status_code("garbage") == 0.0
