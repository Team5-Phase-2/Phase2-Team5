# metrics/ramp_up_time.py
from typing import Optional, Tuple
import time
import requests, math
from src.scoring import _hf_model_id_from_url

def ramp_up_time(model_url: str) -> Tuple[Optional[float], int]:
    """Return (score, latency_ms)."""
    start_ns = time.time_ns()

    try:
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return None, (time.time_ns() - start_ns) // 1_000_000

        try:
            r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if r.status_code != 200:
                return None, (time.time_ns() - start_ns) // 1_000_000
            info = r.json()
        except Exception:
            return None, (time.time_ns() - start_ns) // 1_000_000

        likes = int(info.get("likes") or 0)
        likes_score = min(1.0, max(0.0, (math.log10(1 + likes) / 3.0)))

        siblings = info.get("siblings") or []
        has_readme = any((s.get("rfilename") or "").lower() == "readme.md" for s in siblings)
        has_card = bool(info.get("cardData"))
        readme_score = 1.0 if (has_readme or has_card) else 0.3

        tags = [str(t).lower() for t in (info.get("tags") or [])]
        examples_bonus = 0.1 if any(("example" in t or "tutorial" in t) for t in tags) else 0.0

        score = 0.6 * readme_score + 0.4 * likes_score + examples_bonus
        score = round(min(1.0, max(0.0, score)), 3)

        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
