"""Utilities for normalizing Hugging Face model references.

Only a small helper is exposed: `_hf_model_id_from_url` which accepts
various HF URL forms and returns an `owner/name` or single-segment
model name that's suitable for the Hub API paths.
"""

from __future__ import annotations

from urllib.parse import urlparse


def _hf_model_id_from_url(url: str) -> str:
    """Normalize a Hugging Face model reference to an HF model id.

    Accepts inputs like:
      - https://huggingface.co/bert-base-uncased
      - https://huggingface.co/google/gemma-3-270m/tree/main
      - hf://google/gemma-3-270m
      - google/gemma-3-270m

    Returns either 'owner/name' or a single-segment 'name'. If the URL
    does not look like a HF repo URL the original input is returned so
    callers can decide how to handle it.
    """
    s = url.strip()

    # hf://owner/name or hf://name
    if s.startswith("hf://"):
        tail = s[len("hf://"):].split("/")
        return "/".join(tail[:2]) if len(tail) >= 2 else tail[0]

    # Plain id (owner/name or single-segment)
    if not s.startswith("http"):
        return s

    u = urlparse(s)
    if not u.netloc.endswith("huggingface.co"):
        # Not a HF URL; return as-is so callers can decide
        return s

    parts = [p for p in u.path.lstrip("/").split("/") if p]
    if not parts:
        return s

    # If this is a dataset URL, don't pretend it's a model id
    if parts[0] == "datasets":
        return s

    # Drop non-repo path segments
    drop = {"tree", "blob", "resolve", "commits", "discussions", "files"}
    cleaned = []
    for p in parts:
        if p in drop:
            break
        cleaned.append(p)

    # 1 segment => 'name', 2+ => 'owner/name'
    return cleaned[0] if len(cleaned) == 1 else f"{cleaned[0]}/{cleaned[1]}"