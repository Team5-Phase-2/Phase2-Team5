"""Unit tests for the Run Metrics module.

Tests the net score calculation algorithm including handling of missing metrics,
negative scores, None values, and dictionary-based results from size_score metric.
"""

import pytest
from backend.Rate.run_metrics import calculate_net_score, WEIGHTS


def test_all_metrics_normal_values():
    """All metrics present with valid numeric scores should produce net score of 1.0."""
    results = {name: (1.0, 0) for name in WEIGHTS.keys()}
    score = calculate_net_score(results)
    assert score == 1.0  # all weights sum to 1, so perfect score


def test_missing_some_metrics():
    """Missing metrics should only average over those present."""
    results = {
        "ramp_up_time": (1.0, 0),
        "bus_factor": (0.5, 0),
        # rest missing
    }
    expected = round((1.0 * 0.1 + 0.5 * 0.1) / (0.1 + 0.1), 3)
    assert calculate_net_score(results) == expected


def test_negative_scores_clamped_to_zero():
    """Negative scores should be treated as zero in calculation."""
    results = {
        "ramp_up_time": (-5.0, 0),
        "bus_factor": (0.5, 0),
    }
    expected = round((0 * 0.1 + 0.5 * 0.1) / 0.2, 3)
    assert calculate_net_score(results) == expected


def test_score_none_is_skipped():
    """Score = None should be ignored and not counted."""
    results = {
        "ramp_up_time": (None, 0),
        "bus_factor": (1.0, 0),
    }
    expected = round((1.0 * 0.1) / 0.1, 3)
    assert calculate_net_score(results) == expected


def test_size_score_dict_is_averaged():
    """size_score returns a dict; should compute mean of its values."""
    results = {
        "size_score": ({"a": 0.2, "b": 0.8}, 0),  # mean = 0.5
    }
    expected = round(0.5, 3)  # only one metric with weight 0.1 / 0.1 = 1
    assert calculate_net_score(results) == expected


def test_all_metrics_missing_zero_weight():
    """If no metrics provide a usable score, return 0.0."""
    results = {
        name: (None, 0) for name in WEIGHTS.keys()
    }
    assert calculate_net_score(results) == 0.0


def test_only_nonexistent_metrics_present():
    """If results dict has keys that do not match WEIGHTS, return 0."""
    results = {"not_a_metric": (1.0, 0)}
    assert calculate_net_score(results) == 0.0
