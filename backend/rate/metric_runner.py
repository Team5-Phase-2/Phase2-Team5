# metric_runner.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from metrics.registry import METRIC_REGISTRY
import json
from run_metrics import calculate_net_score

def run_all_metrics(event, context):
    """
    Triggered asynchronously from ArtifactHandler via Destination.
    The data from the first Lambda is found under:
      event["detail"]["responsePayload"]["body"]
    """
    print("Received event from ArtifactHandler:", json.dumps(event))

    try:
        # Step 1: Extract payload from the EventBridge wrapper
        detail = event.get("detail", {})
        payload = detail.get("responsePayload", {})
        body = payload.get("body")

        # Step 2: Parse the inner JSON (your actual return value)
        data = json.loads(body) if body else {}

        artifact_type = data.get("artifact_type")
        model_url = data.get("source_url")

        print(f"Processing artifact: {artifact_type} | URL: {model_url}")

    except Exception as e:
        print("Error in Rate Lambda:", str(e))
        raise

    max_workers = 8
    
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
    
    net_score = calculate_net_score(results)

    # 3. Determine whether to ingest (example rule)
    ingest = True
    for k, (score, latency) in results.items():
        if score < 0.5:
            ingest = False
            break

        

    # 4. Construct output for the next Lambda
    output = {
        "artifact_type": artifact_type,
        "model_url": model_url,
        "results": results,
        "net_score": net_score,
        "ingest": ingest,
    }

    print("Returning output:", json.dumps(output))

    return {
        "statusCode": 200,
        "body": json.dumps(output)
    }
