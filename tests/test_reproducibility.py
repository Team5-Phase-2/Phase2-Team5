# tests/test_reproducibility.py

import json
import importlib
import pytest

import backend.Rate.metrics.reproducibility as rp


@pytest.fixture(autouse=True)
def fresh_reproducibility_module():
    """
    Ensure reproducibility is NOT affected by metric_runner's fake modules.
    This guarantees consistent behavior locally and in CI.
    """
    importlib.reload(rp)
    yield
    importlib.reload(rp)


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

    score, latency = rp.reproducibility("model", "code", "data")

    assert score == 1.0
    assert isinstance(latency, int)


def test_reproducibility_returns_half(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0.5))

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.5


def test_reproducibility_returns_zero(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: _mock_genai_response(0))

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.0


def test_query_genai_error_returns_zero(monkeypatch):
    monkeypatch.setattr(rp, "fetch_hf_readme_text", lambda _: "example code")
    monkeypatch.setattr(rp, "query_genai", lambda _: "Error")

    score, _ = rp.reproducibility("model", "code", "data")

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

    score, _ = rp.reproducibility("model", "code", "data")

    assert score == 0.0


def test_extract_status_code_valid():
    assert rp.extract_status_code("Final Response -- Status Code : 1") == 1.0
    assert rp.extract_status_code("Final Response -- Status Code : 0.5") == 0.5
    assert rp.extract_status_code("Final Response -- Status Code : 0") == 0.0


def test_extract_status_code_invalid():
    assert rp.extract_status_code("garbage") == 0.0
