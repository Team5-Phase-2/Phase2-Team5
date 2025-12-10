
# run_metrics.py
"""backend.Rate.run_metrics

Calculate and aggregate metric scores for a model URL and print results.

Provides:
- `calculate_net_score(results: dict) -> float`: Compute a weighted net score
  from individual metric results using the `WEIGHTS` mapping.

When executed as a script this module runs all metrics for a sample model
URL and prints each metric's score and latency followed by the net score.
"""

WEIGHTS = {
    "ramp_up_time": 0.10,
    "bus_factor": 0.10,
    "performance_claims": 0.10,
    "license": 0.10,
    "size_score": 0.10,
    "dataset_and_code_score": 0.10,
    "dataset_quality": 0.10,
    "code_quality": 0.10,
    "reviewedness": 0.10,
    "reproducibility": 0.10,
}

def calculate_net_score(results: dict) -> float:
    total_weight = 0.0
    net_score = 0.0
    for name, w in WEIGHTS.items():
        r = results.get(name)
        if r is not None:
            score = r[0]
            
            #change to handle size_score returning dict
            if isinstance(score, dict):
                score = sum(score.values()) / len(score)

            if score is not None:
                if score < 0.0:
                    score = 0
                net_score += score * w
                total_weight += w
    return round(net_score / total_weight, 3) if total_weight > 0 else 0.0
