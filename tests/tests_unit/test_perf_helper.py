"""Unit tests for the Performance Helper module.

Tests performance claims detection in model documentation including metric
extraction, date/version filtering, placeholder handling, and markdown table
parsing for model evaluation results.
"""

import pytest
from backend.Rate.perf_helper import (
    has_real_metrics,
    _extract_eval_like_sections,
    _looks_like_metric_table,
)


# ----------------------------------------------------------
# BASIC DETECTION CASES
# ----------------------------------------------------------

def test_detects_simple_metric_near_number():
    """Simple metric keyword near percentage value should be detected."""
    text = "The model achieved accuracy of 92%."
    assert has_real_metrics(text) is True


def test_no_metrics_returns_false():
    """Text without metric keywords should return False."""
    text = "This model description contains no numeric scores."
    assert has_real_metrics(text) is False


def test_metrics_word_without_number_returns_false():
    """Metric keyword without accompanying number should return False."""
    text = "Our accuracy benchmark is described below but no value is given."
    assert has_real_metrics(text) is False


def test_number_without_metric_word_returns_false():
    """Number without metric keyword should return False."""
    text = "The system processed 2048 tokens per batch."
    assert has_real_metrics(text) is False


# ----------------------------------------------------------
# DATE / VERSION FILTER
# ----------------------------------------------------------

def test_ignores_dates_and_versions_as_metrics():
    """Dates and version numbers should not be treated as performance metrics."""
    text = """
    Version 2024-01-05 released.
    Accuracy section coming soon.
    """
    # No meaningful score
    assert has_real_metrics(text) is False


# ----------------------------------------------------------
# PLACEHOLDER BEHAVIOR
# ----------------------------------------------------------

def test_placeholder_skips_section_but_entire_text_has_no_valid_metrics():
    """
    The function does NOT treat 'coming soon' as ignorable
    and does NOT search later sections for real metrics unless
    they contain a metric number + metric word pair.

    So this SHOULD be False with the real implementation.
    """
    text = """
    # Evaluation
    accuracy: coming soon

    # Results
    accuracy improved but no numbers here
    """
    assert has_real_metrics(text) is False


def test_placeholder_only_returns_false():
    """Placeholder text without any metrics should return False."""
    text = """
    evaluation results coming soon, more information needed.
    """
    assert has_real_metrics(text) is False


# ----------------------------------------------------------
# MODEL-INDEX OVERRIDE
# ----------------------------------------------------------
"""model-index metadata with metrics should be detected."""
    
def test_model_index_positive_override():
    text = """
    model-index:
      metrics:
        - name: accuracy
          value: 0.912
    """
    assert has_real_metrics(text) is True


# ----------------------------------------------------------
# SECTION EXTRACTION
# ----------------------------------------------------------

def test_extract_eval_sections_when_headings_match():
    """Evaluation-like sections should be extracted when markdown headings match."""
    text = (
        "# Evaluation\naccuracy 93%\n\n"
        "# Results\nf1 0.88\n"
    )
    sections = _extract_eval_like_sections(text.lower())
    assert len(sections) == 2
    assert "accuracy" in sections[0]
    assert "f1" in sections[1]


def test_extract_eval_no_sections_returns_empty():
    """Text without evaluation-like sections should return empty list."""
    text = "No proper markdown headings here."
    assert _extract_eval_like_sections(text.lower()) == []


# ----------------------------------------------------------
# TABLE DETECTION
# ----------------------------------------------------------

def test_table_with_metric_values():
    """Markdown table with metric header and numeric values should be detected."""
    text = """
| Metric | Accuracy |
|--------|----------|
| ModelA | 92%      |
"""
    # must not indent, or regex won't detect tables
    assert _looks_like_metric_table(text.lower()) is True
    assert has_real_metrics(text) is True


def test_table_with_no_numbers_returns_false():
    """Table with placeholder values instead of numbers should return False."""
    text = """
| Metric | Accuracy |
|--------|----------|
| ModelA | TBD      |
"""
    assert _looks_like_metric_table(text.lower()) is False
    assert has_real_metrics(text) is False


def test_table_with_metric_word_but_header_not_matching():
    """Table without metric keywords in header should not be detected."""
    text = """
| Name | Value |
|------|--------|
| A    | 93%   |
"""
    # header does NOT contain metric words → should not detect
    assert _looks_like_metric_table(text.lower()) is False


def test_metric_word_outside_window_fails():
    """Metric word and number outside proximity window should not be detected."""
    text = "accuracy " + ("x" * 200) + " 95%"
    assert has_real_metrics(text) is False


def test_metric_word_inside_window_succeeds():
    """Metric word and number within proximity window should be detected."""
    text = "accuracy " + ("x" * 50) + " 95%"
    assert has_real_metrics(text) is True


# ----------------------------------------------------------
# COMPLEX MIXED CONTENT
# ----------------------------------------------------------

def test_complex_mixed_readme():
    """Mixed content with table and metric references should be properly detected.
    
    The real code only detects metrics if:
    - metric word AND number coexist in same ~100-char window, OR
    - markdown table is correctly formatted (no indentation)
    """
    text = """
# Benchmark
BLEU improved significantly.
BLEU: 32.5

| Metric | BLEU |
|--------|------|
| M1     | 32.5 |
"""
    # This SHOULD be True because table is valid and not indented
    assert has_real_metrics(text) is True
