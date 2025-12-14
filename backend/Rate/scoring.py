"""backend.Rate.scoring

Utilities for normalizing Hugging Face model URLs and example scoring helpers.

Provides:
- `_hf_model_id_from_url(url: str) -> str`: Convert various HF URL forms into a
  canonical model identifier used by other modules.

The module may contain example/dummy scorer code (disabled) for testing.
"""

# src/scoring.py
from __future__ import annotations
from urllib.parse import urlparse


def _hf_model_id_from_url(url: str) -> str:
    """
    Normalize a Hugging Face model reference to a model_id usable with the Hub API.
    Works for:
      - https://huggingface.co/bert-base-uncased
      - https://huggingface.co/google/gemma-3-270m
      - https://huggingface.co/google/gemma-3-270m/tree/main
      - hf://google/gemma-3-270m
      - google/gemma-3-270m
      - bert-base-uncased
    Returns either 'owner/name' or a single-segment 'name'.
    """
    stripped_url = url.strip()

    # hf://owner/name or hf://name
    if stripped_url.startswith("hf://"):
        tail = stripped_url[len("hf://"):].split("/")
        return "/".join(tail[:2]) if len(tail) >= 2 else tail[0]

    # Plain id (owner/name or single-segment)
    if not stripped_url.startswith("http"):
        return stripped_url

    url_parse = urlparse(stripped_url)
    if not url_parse.netloc.endswith("huggingface.co"):
        # Not a HF URL; return as-is so callers can decide
        return stripped_url

    parts = [part for part in url_parse.path.lstrip("/").split("/") if part]
    if not parts:
        return stripped_url

    # If this is a dataset URL, don't pretend it's a model id
    if parts[0] == "datasets":
        return stripped_url

    # Drop non-repo path segments
    drop = {"tree", "blob", "resolve", "commits", "discussions", "files"}
    cleaned = []
    for part in parts:
        if part in drop:
            break
        cleaned.append(part)

    # 1 segment => 'name', 2+ => 'owner/name'
    return cleaned[0] if len(cleaned) == 1 else f"{cleaned[0]}/{cleaned[1]}"
