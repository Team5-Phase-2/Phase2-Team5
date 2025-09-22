# src/scoring.py
from __future__ import annotations
from typing import Dict, Any
import random
import re

def _hf_model_id_from_url(model_url: str) -> str:
    """
    Extract Hugging Face model ID from URL correctly
    """
    # If it's already just a model ID (no URL), return as is
    if not model_url.startswith(('http://', 'https://')):
        return model_url
    
    # Remove protocol and domain
    if 'huggingface.co/' in model_url:
        # Extract everything after huggingface.co/
        parts = model_url.split('huggingface.co/')
        if len(parts) > 1:
            model_id = parts[1]
            # Remove any trailing slashes or query parameters
            model_id = model_id.rstrip('/')
            if '?' in model_id:
                model_id = model_id.split('?')[0]
            if '#' in model_id:
                model_id = model_id.split('#')[0]
            return model_id
    
    # Fallback: try to extract using regex
    import re
    match = re.search(r'huggingface\.co/([^/?&#]+)', model_url)
    if match:
        return match.group(1)
    
    # If all else fails, return the original (though it will probably fail)
    return model_url

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
