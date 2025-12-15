"""Unit tests for the bus_factor metric.

Tests the bus_factor scoring function which evaluates project activity and
download trends. Verifies error handling, data validation, and scoring logic.
"""

import sys
import importlib
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


sys.modules.setdefault("scoring", importlib.import_module("backend.Rate.scoring"))
sys.modules.setdefault("repo_fetch", importlib.import_module("backend.Rate.repo_fetch"))
sys.modules.setdefault("perf_helper", importlib.import_module("backend.Rate.perf_helper"))

from backend.Rate.metrics.bus_factor import bus_factor


# ======================================================
# TESTS
# ======================================================

def test_model_id_http_prefix_triggers_early_return():
    """Verify that HTTP-prefixed model IDs return zero score immediately."""
    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="http://bad"
    ):
        score, latency = bus_factor("x", None, None)
        assert score == 0.0
        assert isinstance(latency, int)


def test_requests_exception_returns_zero():
    """Verify that network request exceptions result in zero score."""
    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", side_effect=Exception("fail")):
            score, latency = bus_factor("x", None, None)
            assert score == 0.0
            assert isinstance(latency, int)


def test_non_200_status_returns_zero():
    """Verify that non-200 HTTP status codes result in zero score."""
    mock_resp = MagicMock(status_code=404, json=lambda: {})
    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", return_value=mock_resp):
            score, latency = bus_factor("x", None, None)
            assert score == 0.0


def test_downloads_parse_error_sets_zero():
    """Verify that unparseable download counts are handled gracefully."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"downloads": "not-a-number"}

    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", return_value=mock_resp):
            score, latency = bus_factor("x", None, None)
            assert 0.0 <= score <= 1.0
            assert isinstance(latency, int)


def test_invalid_last_modified_sets_default_age():
    """Verify that invalid date formats are handled with default age values."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "downloads": 100,
        "lastModified": "not-a-date",
    }

    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", return_value=mock_resp):
            score, latency = bus_factor("x", None, None)
            assert 0.0 <= score <= 1.0
            assert isinstance(latency, int)


def test_outer_exception_returns_zero():
    """Verify that exceptions in URL parsing result in zero score."""
    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        side_effect=RuntimeError("boom")
    ):
        score, latency = bus_factor("x", None, None)
        assert score == 0.0
        assert isinstance(latency, int)


def test_valid_downloads_and_freshness():
    """Verify that valid download and freshness metrics produce valid scores."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "downloads": 100000,
        "lastModified": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
    }

    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", return_value=mock_resp):
            score, latency = bus_factor("x", None, None)
            assert score > 0.3
            assert isinstance(latency, int)


def test_missing_fields_defaults():
    """Verify that missing API response fields use default values gracefully."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {}

    with patch(
        "backend.Rate.metrics.bus_factor._hf_model_id_from_url",
        return_value="owner/repo"
    ):
        with patch("requests.get", return_value=mock_resp):
            score, latency = bus_factor("x", None, None)
            assert 0.0 <= score <= 1.0
            assert isinstance(latency, int)
