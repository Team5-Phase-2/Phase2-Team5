"""Helpers to extract Hugging Face model repo names.

The public helper `hf_model_repo_name` returns the repository's final
segment (the model name) for a variety of HF URL forms or plain
owner/name strings.
"""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.parse import unquote


def hf_model_repo_name(u: str) -> str:
    """Return the repo name (final model segment) from `u`.

    Examples:
      - https://huggingface.co/google/bert-base-uncased -> bert-base-uncased
      - google/bert-base-uncased -> bert-base-uncased
    """
    s = u.strip()
    # handle plain "org/name" or "name"
    if "://" not in s and not s.startswith("huggingface.co/"):
        parts = [p for p in s.split("/") if p]
    else:
        p = urlparse(s)
        parts = [p for p in p.path.split("/") if p]

    if not parts:
        return ""
    # ignore listing prefixes if they slip in
    if parts[0] in {"models", "spaces", "datasets", "docs", "organizations", "tasks"} and len(parts) >= 2:
        name = parts[1]
    elif len(parts) >= 2:
        name = parts[1]
    else:
        name = parts[0]
    name = unquote(name)
    return name[:-4] if name.endswith(".git") else name
