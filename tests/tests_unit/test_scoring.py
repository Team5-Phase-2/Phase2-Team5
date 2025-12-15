"""Unit tests for the Scoring module.

Tests Hugging Face model ID extraction from various URL formats including
full URLs, hf:// protocol, and plain model ID strings.
"""

import pytest
from backend.Rate.scoring import _hf_model_id_from_url


def test_hf_scheme_with_owner_and_name():
    """hf:// URL with owner/name should extract model ID."""
    assert _hf_model_id_from_url("hf://google/gemma-3-270m") == "google/gemma-3-270m"


def test_hf_scheme_single_segment():
    """hf:// URL with single segment should return as-is."""
    assert _hf_model_id_from_url("hf://bert-base-uncased") == "bert-base-uncased"


def test_plain_model_id_single_segment():
    """Plain single-segment model ID should return as-is."""
    assert _hf_model_id_from_url("bert-base-uncased") == "bert-base-uncased"


def test_plain_model_id_owner_and_name():
    """Plain owner/name format should return as-is."""
    assert _hf_model_id_from_url("google/gemma-3-270m") == "google/gemma-3-270m"


def test_non_http_url_returned_as_is():
    """Non-HTTP URLs should be returned unchanged."""
    assert _hf_model_id_from_url("not_a_url_thing") == "not_a_url_thing"


def test_non_hf_http_url_unchanged():
    """Non-Hugging Face HTTP URLs should be returned unchanged."""
    assert _hf_model_id_from_url("https://example.com/some/model") == \
           "https://example.com/some/model"


def test_hf_simple_model_url():
    """Hugging Face URL with single-segment model ID should extract ID."""
    assert _hf_model_id_from_url("https://huggingface.co/bert-base-uncased") == \
           "bert-base-uncased"


def test_hf_owner_name_url():
    """Hugging Face URL with owner/name should extract ID."""
    assert _hf_model_id_from_url("https://huggingface.co/google/gemma-3-270m") == \
           "google/gemma-3-270m"


def test_hf_url_with_tree_path():
    """Hugging Face URL with /tree/ path should extract owner/name."""
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/tree/main"
    ) == "google/gemma-3-270m"


def test_hf_url_with_blob_path():
    """Hugging Face URL with /blob/ path should extract owner/name."""
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/blob/main/file.txt"
    ) == "google/gemma-3-270m"


def test_hf_url_with_resolve_path():
    """Hugging Face URL with /resolve/ path should extract owner/name."""
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/resolve/main/model.safetensors"
    ) == "google/gemma-3-270m"


def test_hf_url_with_files_path():
    """Hugging Face URL with /files path should extract owner/name."""
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/files"
    ) == "google/gemma-3-270m"


def test_dataset_url_detected_and_returned_as_is():
    """Hugging Face dataset URLs should be returned unchanged."""
    url = "https://huggingface.co/datasets/google/gemma-dataset"
    assert _hf_model_id_from_url(url) == url


def test_hf_url_with_trailing_slash():
    """Hugging Face URL with trailing slash should extract ID."""
    assert _hf_model_id_from_url("https://huggingface.co/google/gemma-3-270m/") == \
           "google/gemma-3-270m"


def test_empty_path_in_hf_url():
    """Hugging Face URL with no path should be returned unchanged."""
    # Example: https://huggingface.co/
    assert _hf_model_id_from_url("https://huggingface.co/") == "https://huggingface.co/"


def test_url_with_extra_segments_before_drop_keyword():
    """Owner/name should be extracted before hitting non-model path keywords."""
    url = "https://huggingface.co/google/gemma-3-270m/commits/main"
    assert _hf_model_id_from_url(url) == "google/gemma-3-270m"
