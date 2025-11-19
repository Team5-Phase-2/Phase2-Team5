"""URL classification helpers used by the `src.url` package.

Return tokens are: ``DATASET``, ``MODEL``, ``CODE`` or ``UNKNOWN``.
"""

from __future__ import annotations

import re


# Hugging Face datasets
HF_DATASET_RE = re.compile(r"^https?://huggingface\.co/datasets/[^/]+/[^/\s]+(?:$|[/?#])")

# Hugging Face models (two segments: org/name)
HF_MODEL_TWO = re.compile(r"^https?://huggingface\.co/(?!datasets/)[^/\s]+/[^/\s]+(?:$|[/?#])")
# Single-segment model (https://huggingface.co/name)
HF_MODEL_ONE = re.compile(r"^https?://huggingface\.co/(?!datasets/)([^/\s?#]+)(?:$|[/?#])")

# GitHub repos
GITHUB_RE = re.compile(r"^https?://github\.com/[^/]+/[^/\s]+(?:$|[/?#])")


def classify(url: str) -> str:
    """Return the kind of `url` as one of: DATASET, MODEL, CODE, UNKNOWN."""
    u = url.strip()
    if HF_DATASET_RE.match(u):
        return "DATASET"
    if HF_MODEL_TWO.match(u) or HF_MODEL_ONE.match(u):
        return "MODEL"
    if GITHUB_RE.match(u):
        return "CODE"
    return "UNKNOWN"

