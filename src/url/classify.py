# src/url/classify.py
import re

# Hugging Face datasets
HF_DATASET_RE = re.compile(
    r"^https?://huggingface\.co/datasets/[^/]+/[^/\s]+(?:$|[/?#])"
)

# Hugging Face models:
# - two segments: https://huggingface.co/org/name
HF_MODEL_TWO = re.compile(
    r"^https?://huggingface\.co/(?!datasets/)[^/\s]+/[^/\s]+(?:$|[/?#])"
)
# - one segment: https://huggingface.co/name
HF_MODEL_ONE = re.compile(
    r"^https?://huggingface\.co/(?!datasets/)([^/\s?#]+)(?:$|[/?#])"
)

# GitHub repos
GITHUB_RE = re.compile(
    r"^https?://github\.com/[^/]+/[^/\s]+(?:$|[/?#])"
)

def classify(url: str) -> str:
    u = url.strip()
    if HF_DATASET_RE.match(u):
        return "DATASET"
    if HF_MODEL_TWO.match(u) or HF_MODEL_ONE.match(u):
        return "MODEL"
    if GITHUB_RE.match(u):
        return "CODE"
    return "UNKNOWN"

