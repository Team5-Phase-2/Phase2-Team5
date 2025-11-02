# metric_runner.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from metrics.registry import METRIC_REGISTRY


def run_all_metrics(model_url: str, max_workers: int = 8) -> Dict[str, Tuple[float, int]]:
    
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(fn, model_url): key
            for key, fn in METRIC_REGISTRY
        }

        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                score_latency = future.result()
                
                if isinstance(score_latency, tuple) and len(score_latency) == 2:
                    results[key] = score_latency
                else:
                    results[key] = (score_latency, 0)
            except Exception:
                results[key] = (None, 0)
    return results
