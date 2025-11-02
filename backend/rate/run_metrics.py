# run_metrics.py
from metric_runner import run_all_metrics

WEIGHTS = {
    "ramp_up_time": 0.15,
    "bus_factor": 0.10,
    "performance_claims": 0.15,
    "license": 0.15,
    "size_score": 0.15,
    "dataset_and_code_score": 0.10,
    "dataset_quality": 0.10,
    "code_quality": 0.10,
}

def calculate_net_score(results: dict) -> float:
    total_weight = 0.0
    net_score = 0.0
    for name, w in WEIGHTS.items():
        r = results.get(name)
        if r is not None:
            score = r[0]
            if score is not None:
                net_score += score * w
                total_weight += w
    return round(net_score / total_weight, 3) if total_weight > 0 else 0.0


if __name__ == "__main__":
    
    model_url = "https://huggingface.co/parvk11/audience_classifier_model"
    results = run_all_metrics(model_url)
    for k, (score, latency) in results.items():
        print(f"{k:25s} -> score: {str(score):6s}   latency_ms: {latency}")
    print("\nNet score:", calculate_net_score(results))
