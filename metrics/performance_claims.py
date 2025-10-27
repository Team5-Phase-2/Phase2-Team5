# metrics/performance_claims.py
from typing import Optional, Tuple
import time
from src.repo_fetch import download_hf_repo_subset, read_text_if_exists
from src.perf_helper import has_real_metrics

def performance_claims(model_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        repo_dir = download_hf_repo_subset(model_url)
        for name in ("README.md", "model_index.json", "README.yaml"):
            text = read_text_if_exists(repo_dir, name)
            if text and text.strip():
                score = 1.0 if has_real_metrics(text) else 0.0
                latency_ms = (time.time_ns() - start_ns) // 1_000_000
                return score, latency_ms
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return 0.0, latency_ms
    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
