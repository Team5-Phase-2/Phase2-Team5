import math
from src.metrics_framework import (
    MetricsCalculator,
    MetricResult,
    SizeMetric,
    DatasetQualityMetric,
    DatasetCodeMetric,
    CodeQualityMetric,
    BaseMetric,
    LicenseMetric
)

SAMPLE_MODEL = "https://huggingface.co/google-bert/bert-base-uncased"
BAD_MODEL    = "https://huggingface.co/this-org/definitely-not-a-real-model-xyz"


def _assert_score_range_or_none(score):
    if score is None:
        return
    assert isinstance(score, float)
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


def _assert_latency(lat):
    assert isinstance(lat, int)
    assert lat >= 0


def test_calculate_all_metrics_basic_shape():
    calc = MetricsCalculator()
    results = calc.calculate_all_metrics(SAMPLE_MODEL)
    # Has all expected keys
    expected = {
        "ramp_up_time",
        "bus_factor",
        "license",
        "performance_claims",
        "size_score",
        "dataset_and_code_score",
        "dataset_quality",
        "code_quality",
    }
    assert expected.issubset(results.keys())
    # Each value is a MetricResult with sensible fields
    for k, v in results.items():
        assert isinstance(v, MetricResult)
        _assert_score_range_or_none(v.score)
        _assert_latency(v.latency_ms)


def test_calculate_net_score_weights_and_missing():
    # Build a fake dict to exercise weighting + None handling paths
    calc = MetricsCalculator()
    fake = {
        "ramp_up_time":       MetricResult(1.0, 1),
        "bus_factor":         MetricResult(0.5, 1),
        "performance_claims": MetricResult(None, 1),  # skipped
        "license":            MetricResult(0.0, 1),
        "size_score":         MetricResult(0.25, 1),
        "dataset_and_code_score": MetricResult(1.0, 1),
        "dataset_quality":    MetricResult(0.6, 1),
        "code_quality":       MetricResult(0.75, 1),
    }
    net = calc.calculate_net_score(fake)
    assert isinstance(net, float)
    assert 0.0 <= net <= 1.0

    # If everything is None, net score should be 0.0 (defensive path)
    all_none = {k: MetricResult(None, 0) for k in fake.keys()}
    net2 = calc.calculate_net_score(all_none)
    assert net2 == 0.0


def test_dataset_metrics_also_return_scores_and_latency():
    # Keep parity with your simple pattern, just cover the two extra metrics too
    dq = DatasetQualityMetric().calculate(SAMPLE_MODEL)
    _assert_score_range_or_none(dq.score)
    _assert_latency(dq.latency_ms)

    dcs = DatasetCodeMetric().calculate(SAMPLE_MODEL)
    _assert_score_range_or_none(dcs.score)
    _assert_latency(dcs.latency_ms)


def test_size_metric_exposes_device_scores_after_run():
    sm = SizeMetric()
    res = sm.calculate(SAMPLE_MODEL)
    _assert_score_range_or_none(res.score)
    _assert_latency(res.latency_ms)

    # If a score was computed, device_scores should be a non-empty dict with known keys
    # (If None due to network hiccup, we just skip the stricter assertions.)
    if res.score is not None and hasattr(sm, "device_scores"):
        assert isinstance(sm.device_scores, dict)
        # The metric always populates these four when total size is known
        expected_keys = {"raspberry_pi", "jetson_nano", "desktop_pc", "aws_server"}
        assert expected_keys.issubset(set(sm.device_scores.keys()))
        for v in sm.device_scores.values():
            assert 0.0 <= float(v) <= 1.0


def test_code_quality_parse_thresholds_offline_only():
    # Pure function coverage: no network, no subprocess
    parser = CodeQualityMetric()._parse_pylint_score

    # The implementation buckets scores; hit each bucket minimally
    assert parser("Your code has been rated at 9.99/10 (prev)") == 1.0
    assert parser("Your code has been rated at 7.00/10 (prev)") == 1.0
    assert parser("Your code has been rated at 4.50/10 (prev)") == 0.75
    assert parser("Your code has been rated at 2.00/10 (prev)") == 0.5
    assert parser("Your code has been rated at 0.20/10 (prev)") == 0.25
    assert parser("Your code has been rated at 0.00/10 (prev)") is None
    # Garbage lines should safely return None
    assert parser("no score here") is None


def test_base_metric_error_path_latency_is_int():
    # Tiny concrete subclass that raises to hit BaseMetric error handling
    class Explode(BaseMetric):
        def __init__(self): super().__init__("explode")
        def _calculate_score(self, model_url: str):
            raise RuntimeError("boom")

    m = Explode()
    res = m.calculate(SAMPLE_MODEL)
    assert res.score is None
    _assert_latency(res.latency_ms)
def _is_score(x):
    return (x is None) or (isinstance(x, float) and math.isfinite(x) and 0.0 <= x <= 1.0)

def test_all_metrics_present_and_net_score_with_bad_model():
    """
    Simple sanity test on a bad/non-existent model:
    - Every metric should still return a MetricResult
    - Scores must be None or in [0,1]
    - Latencies are non-negative integers
    - calculate_net_score should return a bounded float (often low, but defined)
    This hits the calculator loop paths where some metrics yield None.
    """
    calc = MetricsCalculator()

    results = calc.calculate_all_metrics(BAD_MODEL)
    assert isinstance(results, dict)
    # Expected keys present
    expected = {
        "ramp_up_time",
        "bus_factor",
        "license",
        "performance_claims",
        "size_score",
        "dataset_and_code_score",
        "dataset_quality",
        "code_quality",
    }
    assert expected.issubset(results.keys())

    # Validate shape and ranges
    for name, res in results.items():
        assert isinstance(res, MetricResult), f"{name} did not return MetricResult"
        assert _is_score(res.score), f"{name} score out of range"
        assert isinstance(res.latency_ms, int) and res.latency_ms >= 0, f"{name} bad latency"

    # Even with many None scores, net score should be a valid float in [0,1]
    net = calc.calculate_net_score(results)
    assert isinstance(net, float)
    assert 0.0 <= net <= 1.0

def test_net_score_with_empty_results_returns_zero():
    """
    If the caller passes an empty dict, the calculator should defensively return 0.0.
    This executes the 'no weights accumulated' branch.
    """
    calc = MetricsCalculator()
    assert calc.calculate_net_score({}) == 0.0

_LICENSE_MODELS = [
    # Often have a "## License" section text (not just YAML)
    "https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2",
    "https://huggingface.co/tiiuae/falcon-7b-instruct",
]

_DATASET_MODELS_TWO_PLUS = [
    # Likely to mention at least two trusted datasets (e.g., LibriSpeech + Common Voice)
    "https://huggingface.co/openai/whisper-base",
]

_DATASET_MODELS_ONE = [
    # Commonly mention a single trusted dataset (e.g., ImageNet or LibriSpeech)
    "https://huggingface.co/facebook/wav2vec2-base-960h",
    "https://huggingface.co/google/vit-base-patch16-224",
]

_DATASET_MODELS_FALLBACK = [
    # Likely to include a Datasets section or cardData without trusted names (hits api_ds or sec fallback)
    "https://huggingface.co/distilbert/distilbert-base-uncased",
]

def test_license_metric_section_or_fallback_paths_execute():
    lm = LicenseMetric()
    # We don't assert exact values (since cards evolve), only that a valid score is produced
    # which exercises either the "License section" branch or the "fallback scan" branch.
    for url in _LICENSE_MODELS:
        res = lm.calculate(url)
        assert res.score is not None
        assert 0.0 <= float(res.score) <= 1.0
        assert isinstance(res.latency_ms, int) and res.latency_ms >= 0


