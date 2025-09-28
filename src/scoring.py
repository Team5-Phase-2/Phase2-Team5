# src/scoring.py
from __future__ import annotations
from typing import Dict, Any
from urllib.parse import urlparse

import random
import re

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

    

def score_model(model_url: str, *, cache_dir: str | None = None, parallelism: int = 8) -> Dict[str, Any]:
    """
    Dummy scorer for smoke-testing stdout.
    Produces deterministic pseudo-random values in [0,1] based on the model id.
    Returns only a few fields; your NDJSON writer's template can fill the rest.
    """
    model_id = _hf_model_id_from_url(model_url)

    # deterministic RNG so the same model gets the same "random" scores
    seed = hash(model_id) & 0xFFFFFFFF
    rng = random.Random(seed)

    ramp_up_time = round(rng.random(), 3)  # 0..1
    license_score = round(rng.random(), 3) # 0..1
    net_score = round((ramp_up_time + license_score) / 2.0, 3)

    return {
        "ramp_up_time": ramp_up_time,
        "ramp_up_time_latency": rng.randint(1, 25),  # milliseconds
        "license": license_score,
        "license_latency": rng.randint(1, 25),       # milliseconds
        "net_score": net_score,
        "net_score_latency": rng.randint(5, 60),     # milliseconds
    }
