import pytest
from backend.Rate.scoring import _hf_model_id_from_url

@pytest.mark.parametrize("u,expect", [
    ("https://huggingface.co/google/gemma-3-270m", "google/gemma-3-270m"),
    ("https://huggingface.co/google/gemma-3-270m/tree/main", "google/gemma-3-270m"),
    ("google/gemma-3-270m", "google/gemma-3-270m"),
    (" hf://google/gemma-3-270m ", "google/gemma-3-270m"),
])
def test_hf_id_good(u, expect):
    assert _hf_model_id_from_url(u) == expect

