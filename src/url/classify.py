#decide MODEL/DATASET/CODE URL

from __future__ import annotations
import re

HF_MODEL_RE   = re.compile(r"^https?://huggingface\.co/(?!datasets/)[^/]+/[^/\s]+")
HF_DATASET_RE = re.compile(r"^https?://huggingface\.co/datasets/[^/]+/[^/\s]+")
GITHUB_RE     = re.compile(r"^https?://github\.com/[^/]+/[^/\s]+")

def classify(url: str) -> str:
    """Return one of: MODEL, DATASET, CODE, UNKNOWN"""
    u = url.strip()
    if HF_DATASET_RE.match(u):
        return "DATASET"
    if HF_MODEL_RE.match(u):
        return "MODEL"
    if GITHUB_RE.match(u):
        return "CODE"
    return "UNKNOWN"
