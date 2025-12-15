"""
Unit tests for size_score metric.
"""

import pytest
from unittest.mock import MagicMock
import backend.Rate.metrics.size_score as ss


class MockResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    def json(self):
        return self._json


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Centralized mock for requests.get and requests.head.
    Each test fills in expected URLs.
    """
    get_calls = {}
    head_calls = {}

    def fake_get(url, *args, **kwargs):
        if url not in get_calls:
            raise AssertionError(f"Unexpected GET request: {url}")
        return get_calls[url]

    def fake_head(url, *args, **kwargs):
        if url not in head_calls:
            raise AssertionError(f"Unexpected HEAD request: {url}")
        return head_calls[url]

    monkeypatch.setattr(ss.requests, "get", fake_get)
    monkeypatch.setattr(ss.requests, "head", fake_head)

    return get_calls, head_calls


@pytest.fixture(autouse=True)
def mock_model_id(monkeypatch):
    """Mock the Hugging Face model ID extraction function."""
    monkeypatch.setattr(ss, "_hf_model_id_from_url", lambda _: "owner/model")


def test_non_hf_url_returns_none(monkeypatch):
    """Non-Hugging Face URLs should return None score."""
    monkeypatch.setattr(ss, "_hf_model_id_from_url", lambda _: "http://example.com")

    score, latency = ss.size_score("http://example.com", "", "")

    assert score is None
    assert isinstance(latency, int)


def test_metadata_api_failure_returns_none(mock_requests):
    get_calls, _ = mock_requests

    get_calls["https://huggingface.co/api/models/owner/model"] = MockResponse(
        status_code=500
    )

    score, latency = ss.size_score("model", "", "")

    assert score is None
    assert isinstance(latency, int)


def test_missing_sha_or_siblings_returns_none(mock_requests):
    get_calls, _ = mock_requests

    get_calls["https://huggingface.co/api/models/owner/model"] = MockResponse(
        json_data={"siblings": []}
    )

    score, latency = ss.size_score("model", "", "")

    assert score is None
    assert isinstance(latency, int)


def test_no_weight_files_returns_none(mock_requests):
    get_calls, _ = mock_requests

    get_calls["https://huggingface.co/api/models/owner/model"] = MockResponse(
        json_data={
            "sha": "abc",
            "siblings": [{"rfilename": "README.md"}],
        }
    )

    score, latency = ss.size_score("model", "", "")

    assert score is None
    assert isinstance(latency, int)


def test_large_model_caps_at_zero(mock_requests):
    get_calls, head_calls = mock_requests

    get_calls["https://huggingface.co/api/models/owner/model"] = MockResponse(
        json_data={
            "sha": "abc",
            "siblings": [
                {"rfilename": "model.bin"},
                {"rfilename": "model2.bin"},
            ],
        }
    )

    big = 80 * (1024 ** 3)

    head_calls[
        "https://huggingface.co/owner/model/resolve/abc/model.bin"
    ] = MockResponse(headers={"Content-Length": str(big)})

    head_calls[
        "https://huggingface.co/owner/model/resolve/abc/model2.bin"
    ] = MockResponse(headers={"Content-Length": str(big)})

    score, latency = ss.size_score("model", "", "")

    assert score["raspberry_pi"] == 0.0
    assert score["aws_server"] == 0.0
    assert isinstance(latency, int)


def test_head_failure_fallback_to_range_get(mock_requests):
    get_calls, head_calls = mock_requests

    get_calls["https://huggingface.co/api/models/owner/model"] = MockResponse(
        json_data={
            "sha": "abc",
            "siblings": [{"rfilename": "model.bin"}],
        }
    )

    head_calls[
        "https://huggingface.co/owner/model/resolve/abc/model.bin"
    ] = MockResponse(headers={})

    get_calls[
        "https://huggingface.co/owner/model/resolve/abc/model.bin"
    ] = MockResponse(headers={"Content-Range": "bytes 0-0/2147483648"})

    score, latency = ss.size_score("model", "", "")

    assert score["desktop_pc"] == 1.0
    assert isinstance(latency, int)


def test_exception_returns_none(monkeypatch):
    monkeypatch.setattr(ss.requests, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError))

    score, latency = ss.size_score("model", "", "")

    assert score is None
    assert isinstance(latency, int)
