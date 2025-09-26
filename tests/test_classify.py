import pytest
from src.url.classify import classify

@pytest.mark.parametrize("u,kind", [
    ("https://huggingface.co/google/gemma-3-270m", "MODEL"),
    ("https://huggingface.co/google/gemma-3-270m/tree/main", "MODEL"),
    ("https://huggingface.co/datasets/xlangai/AgentNet", "DATASET"),
    ("https://github.com/SkyworkAI/Matrix-Game", "CODE"),
    ("https://github.com/user/repo", "CODE"),
    (" https://huggingface.co/datasets/foo/bar ", "DATASET"),
    ("https://example.com/whatever", "UNKNOWN"),
    ("not a url", "UNKNOWN"),
])
def test_classify(u, kind):
    assert classify(u) == kind
