# tests/test_reproducibility.py

import json
import pytest

import backend.Rate.metrics.reproducibility as rp
from backend.Rate.metrics.reproducibility import reproducibility


def _mock_genai_response(status_code: float):
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


def test_reproducibility_returns_one(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "```python\nprint('hi')\n```")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(1))

    score, latency = reproducibility("model", "code", "data")

    assert score == 1.0
    assert isinstance(latency, int)


def test_reproducibility_returns_half(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0.5))

    score, _ = reproducibility("model", "code", "data")

    assert score == 0.5


def test_reproducibility_returns_zero(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0))

    score, _ = reproducibility("model", "code", "data")

    assert score == 0.0


def test_query_genai_error_returns_zero(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: "Error")

    score, _ = reproducibility("model", "code", "data")

    assert score == 0.0


def test_missing_status_code_returns_zero(monkeypatch):
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

    score, _ = reproducibility("model", "code", "data")

    assert score == 0.0


def test_extract_status_code_valid():
    extract = rp.extract_status_code
    assert extract("Final Response -- Status Code : 1") == 1.0
    assert extract("Final Response -- Status Code : 0.5") == 0.5
    assert extract("Final Response -- Status Code : 0") == 0.0


def test_extract_status_code_invalid():
    extract = rp.extract_status_code
    assert extract("garbage") == 0.0
