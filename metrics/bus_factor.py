# metrics/bus_factor.py
from typing import Optional, Tuple
import time
import requests, math
from datetime import datetime
from src.scoring import _hf_model_id_from_url

def bus_factor(model_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return 0.0, (time.time_ns() - start_ns) // 1_000_000

        try:
            r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if r.status_code != 200:
                return 0.0, (time.time_ns() - start_ns) // 1_000_000
            info = r.json()
        except Exception:
            return 0.0, (time.time_ns() - start_ns) // 1_000_000

        downloads = 0
        try:
            downloads = int(info.get("downloads") or 0)
        except Exception:
            downloads = 0
        downloads_norm = min(1.0, math.log10(1 + downloads) / 6.0)

        last_mod = info.get("lastModified")
        age_days = 365.0
        if isinstance(last_mod, str):
            s = last_mod.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
                import time as _time
                age_days = max(0.0, (_time.time() - dt.timestamp()) / 86400.0)
            except Exception:
                age_days = 365.0
        freshness = max(0.0, min(1.0, 1.0 - (age_days / 365.0)))

        score = round(0.6 * downloads_norm + 0.4 * freshness, 3)
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return 0.0, latency_ms
