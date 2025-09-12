# src/scoring.py
from __future__ import annotations
from typing import Dict, Any
import random
import re

def _hf_model_id_from_url(url: str) -> str:
    """
    Minimal normalization so the same URL yields stable random scores.
    If it's a HF model URL like https://huggingface.co/org/name(/...),
    we return 'org/name'. Otherwise we just return the input string.
    """
    m = re.match(r"^https?://huggingface\.co/(?!datasets/)([^/]+)/([^/\s]+)", url.strip())
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return url.strip()

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
