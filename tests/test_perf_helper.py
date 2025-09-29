# tests/test_perf_helper_simple.py
import pytest

from src.perf_helper import (
    has_real_metrics,
    _has_real_metrics,
    _extract_eval_like_sections,
    _looks_like_metric_table,
)


def test_model_index_block_triggers_true():
    text = """
---
model-index:
  - name: MyModel
    results:
      - task:
          type: text-classification
        dataset:
          name: imdb
        metrics:
          - name: accuracy
            type: acc
            value: 92.3
"""
    assert has_real_metrics(text) is True
    assert _has_real_metrics(text) is True


def test_placeholder_in_section_does_not_trigger():
    text = """
# Evaluation
More information needed
"""
    assert has_real_metrics(text) is False


def test_no_numbers_returns_false():
    text = "We evaluated on GLUE but provide no numbers yet."
    assert has_real_metrics(text) is False


def test_extract_eval_like_sections_finds_headings():
    text = """
Intro text

## Evaluation
Body A

### Benchmarks
Body B

## Something Else
Body C
"""
    sections = _extract_eval_like_sections(text.lower())
    assert isinstance(sections, list)
    assert len(sections) >= 2
    assert "evaluation" in sections[0]
    assert "benchmarks" in sections[1]