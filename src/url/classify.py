
"""
classify.py
-----------

This module decides what type of URL we are looking at.

Functions:
- classify(url: str) -> str

It uses regex rules to check:
- Hugging Face dataset URLs → return "DATASET"
- Hugging Face model URLs (not datasets) → return "MODEL"
- GitHub repo URLs → return "CODE"
- Anything else → return "UNKNOWN"

Example:
    classify("https://huggingface.co/google/gemma-3-270m")  -> "MODEL"
    classify("https://huggingface.co/datasets/xlangai/AgentNet") -> "DATASET"
    classify("https://github.com/SkyworkAI/Matrix-Game")   -> "CODE"
    classify("https://example.com/foo")                    -> "UNKNOWN"
"""


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
