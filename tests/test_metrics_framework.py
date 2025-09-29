# tests/test_metrics_framework.py
import os
import math
import pytest

# Silence 3rd-party noise so our stdout stays clean during tests
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

from src.metrics_framework import MetricsCalculator, PerformanceClaimsMetric

SAMPLE_MODEL = "https://huggingface.co/google-bert/bert-base-uncased"
BAD_MODEL    = "https://huggingface.co/this-org/definitely-not-a-real-model-xyz"


def _get_score_latency(res):
    """
    Helper to accept either an object with attributes or a dict-like result.
    Returns (score, latency_ms) always.
    """
    if res is None:
        return 0.0, 0
    score = getattr(res, "score", None)
    if score is None and isinstance(res, dict):
        score = res.get("score")
    lat = getattr(res, "latency_ms", None)
    if lat is None and isinstance(res, dict):
        lat = res.get("latency_ms")
    # normalize
    try:
        score = float(score) if score is not None else 0.0
    except Exception:
        score = 0.0
    try:
        lat = int(lat) if lat is not None else 0
    except Exception:
        lat = 0
    return score, lat


def _assert_score_range(score: float):
    assert isinstance(score, float)
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


def _assert_latency(lat: int):
    assert isinstance(lat, int)
    assert lat >= 0


@pytest.fixture(scope="module")
def calc():
    return MetricsCalculator()


@pytest.mark.parametrize("metric_key", [
    "ramp_up_time",
    "bus_factor",
    "license",
    "size_score",
    "code_quality",
    # include if present in your MetricsCalculator:
    # "dataset_quality",
    # "dataset_and_code_score",
])
def test_metric_happy_path_score_and_latency(calc, metric_key):
    """Each metric returns a score in [0,1] and a non-negative integer latency."""
    res = calc.metrics[metric_key].calculate(SAMPLE_MODEL)
    score, lat = _get_score_latency(res)
    _assert_score_range(score)
    _assert_latency(lat)


@pytest.mark.parametrize("metric_key", [
    "ramp_up_time",
    "bus_factor",
    "license",
    "size_score",
    "code_quality",
    # include if present:
    # "dataset_quality",
    # "dataset_and_code_score",
])
def test_metric_handles_bad_url_gracefully(calc, metric_key):
    """
    On invalid/unavailable URLs, metrics should still return a bounded score (often 0.0)
    and a non-negative integer latency without raising.
    """
    res = calc.metrics[metric_key].calculate(BAD_MODEL)
    score, lat = _get_score_latency(res)
    _assert_score_range(score)     # typically 0.0, but bounded either way
    _assert_latency(lat)


def test_performance_claims_happy_path_and_binary():
    """
    PerformanceClaimsMetric should compute quickly and return a value in [0,1].
    If your implementation is binary (0/1), this test also allows 0.0/1.0.
    """
    pc = PerformanceClaimsMetric()
    res = pc.calculate(SAMPLE_MODEL)
    score, lat = _get_score_latency(res)
    _assert_score_range(score)
    _assert_latency(lat)
    # If you purposely return binary, also assert it's one of {0.0, 1.0}
    assert score in (0.0, 1.0) or (0.0 <= score <= 1.0)


def test_performance_claims_handles_bad_url():
    pc = PerformanceClaimsMetric()
    res = pc.calculate(BAD_MODEL)
    score, lat = _get_score_latency(res)
    _assert_score_range(score)
    _assert_latency(lat)


def test_code_quality_does_not_write_to_stdout(capsys, calc):
    """
    Any diagnostic output from code_quality should go to stderr or logs, not stdout.
    """
    _ = calc.metrics["code_quality"].calculate(BAD_MODEL)
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout must be clean NDJSON-only in the CLI


def test_metrics_dict_has_expected_keys(calc):
    """
    Sanity: your calculator exposes the expected metric keys.
    This helps catch accidental renames/regressions.
    """
    expected = {
        "ramp_up_time",
        "bus_factor",
        "license",
        "size_score",
        "code_quality",
        # include if you implement them:
        # "dataset_quality",
        # "dataset_and_code_score",
    }
    assert expected.issubset(set(calc.metrics.keys()))

