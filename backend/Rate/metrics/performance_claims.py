"""backend.Rate.metrics.performance_claims

Detect whether a model repository advertises performance claims (numeric
metrics) in common files like README or model_index.json. Returns 1.0 if
claims are detected, 0.0 if not, or None on error.
"""

from typing import Optional, Tuple
import time
from repo_fetch import download_hf_repo_subset, read_text_if_exists
from perf_helper import has_real_metrics


def performance_claims(model_url: str) -> Tuple[Optional[float], int]:
    """Return (score, latency_ms) where score is 1.0 if numeric performance
    claims are present, otherwise 0.0.
    """

    start_ns = time.time_ns()
    try:
        # Download a small set of likely files and inspect them
        repo_dir = download_hf_repo_subset(model_url)
        for name in ("README.md", "model_index.json", "README.yaml"):
            text = read_text_if_exists(repo_dir, name)
            if text and text.strip():
                score = 1.0 if has_real_metrics(text) else 0.0
                latency_ms = (time.time_ns() - start_ns) // 1_000_000
                return score, latency_ms

        # No readable files found -> no claims
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return 0.0, latency_ms
    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
