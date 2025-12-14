import sys
import types
import pathlib
import importlib.util
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ======================================================
# 1. Inject fake scoring BEFORE loading bus_factor
# ======================================================
fake_scoring = types.ModuleType("scoring")
fake_scoring._hf_model_id_from_url = lambda url: "owner/repo"
sys.modules["scoring"] = fake_scoring


# ======================================================
# 2. Load bus_factor.py DIRECTLY (no package import)
# ======================================================
BUS_FACTOR_PATH = pathlib.Path(
    "backend/Rate/metrics/bus_factor.py"
).resolve()

MODULE_NAME = "backend.Rate.metrics.bus_factor"

spec = importlib.util.spec_from_file_location(MODULE_NAME, BUS_FACTOR_PATH)
bus_factor_module = importlib.util.module_from_spec(spec)

# Register BEFORE executing so coverage maps correctly
sys.modules[MODULE_NAME] = bus_factor_module

spec.loader.exec_module(bus_factor_module)

bus_factor = bus_factor_module.bus_factor


# ======================================================
# TESTS
# ======================================================

def test_non_hf_url_returns_zero_score():
    bus_factor_module._hf_model_id_from_url = lambda url: "http://bad"
    score, latency = bus_factor("x", None, None)
    assert score == 0.0
    assert isinstance(latency, int)


def test_requests_http_error_returns_zero():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    with patch("requests.get", side_effect=Exception("fail")):
        score, latency = bus_factor("x", None, None)
        assert score == 0.0
        assert isinstance(latency, int)


def test_non_200_status_returns_zero():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    mock_resp = MagicMock(status_code=404, json=lambda: {})
    with patch("requests.get", return_value=mock_resp):
        score, latency = bus_factor("x", None, None)
        assert score == 0.0


def test_downloads_parse_error_sets_zero():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"downloads": "not-a-number"}

    with patch("requests.get", return_value=mock_resp):
        score, latency = bus_factor("x", None, None)
        assert 0.0 <= score <= 1.0


def test_invalid_last_modified_sets_age_default():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "downloads": 100,
        "lastModified": "bad-date",
    }

    with patch("requests.get", return_value=mock_resp):
        score, latency = bus_factor("x", None, None)
        assert 0.0 <= score <= 1.0


def test_outer_exception_returns_zero_score():
    def explode(_):
        raise RuntimeError("boom")

    bus_factor_module._hf_model_id_from_url = explode

    score, latency = bus_factor("x", None, None)
    assert score == 0.0
    assert isinstance(latency, int)


def test_valid_downloads_and_freshness():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "downloads": 100_000,
        "lastModified": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    }

    with patch("requests.get", return_value=mock_resp):
        score, latency = bus_factor("x", None, None)
        assert score > 0.3
        assert isinstance(latency, int)


def test_missing_fields_defaults():
    bus_factor_module._hf_model_id_from_url = lambda url: "owner/repo"

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {}

    with patch("requests.get", return_value=mock_resp):
        score, latency = bus_factor("x", None, None)
        assert 0.0 <= score <= 1.0
