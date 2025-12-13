import pytest
from backend.rate.scoring import _hf_model_id_from_url


def test_hf_scheme_with_owner_and_name():
    assert _hf_model_id_from_url("hf://google/gemma-3-270m") == "google/gemma-3-270m"


def test_hf_scheme_single_segment():
    assert _hf_model_id_from_url("hf://bert-base-uncased") == "bert-base-uncased"


def test_plain_model_id_single_segment():
    assert _hf_model_id_from_url("bert-base-uncased") == "bert-base-uncased"


def test_plain_model_id_owner_and_name():
    assert _hf_model_id_from_url("google/gemma-3-270m") == "google/gemma-3-270m"


def test_non_http_url_returned_as_is():
    assert _hf_model_id_from_url("not_a_url_thing") == "not_a_url_thing"


def test_non_hf_http_url_unchanged():
    assert _hf_model_id_from_url("https://example.com/some/model") == \
           "https://example.com/some/model"


def test_hf_simple_model_url():
    assert _hf_model_id_from_url("https://huggingface.co/bert-base-uncased") == \
           "bert-base-uncased"


def test_hf_owner_name_url():
    assert _hf_model_id_from_url("https://huggingface.co/google/gemma-3-270m") == \
           "google/gemma-3-270m"


def test_hf_url_with_tree_path():
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/tree/main"
    ) == "google/gemma-3-270m"


def test_hf_url_with_blob_path():
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/blob/main/file.txt"
    ) == "google/gemma-3-270m"


def test_hf_url_with_resolve_path():
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/resolve/main/model.safetensors"
    ) == "google/gemma-3-270m"


def test_hf_url_with_files_path():
    assert _hf_model_id_from_url(
        "https://huggingface.co/google/gemma-3-270m/files"
    ) == "google/gemma-3-270m"


def test_dataset_url_detected_and_returned_as_is():
    url = "https://huggingface.co/datasets/google/gemma-dataset"
    assert _hf_model_id_from_url(url) == url


def test_hf_url_with_trailing_slash():
    assert _hf_model_id_from_url("https://huggingface.co/google/gemma-3-270m/") == \
           "google/gemma-3-270m"


def test_empty_path_in_hf_url():
    # Example: https://huggingface.co/
    assert _hf_model_id_from_url("https://huggingface.co/") == "https://huggingface.co/"


def test_url_with_extra_segments_before_drop_keyword():
    # Owner/name should still be extracted before hitting drop keyword
    url = "https://huggingface.co/google/gemma-3-270m/commits/main"
    assert _hf_model_id_from_url(url) == "google/gemma-3-270m"
