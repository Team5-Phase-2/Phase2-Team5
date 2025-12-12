"""backend.Rate.metric_runner

Run registered metrics concurrently for a given model URL, aggregate
results and invoke the Upload/ingestor lambda. Exposes `run_all_metrics`
which accepts an event and context and returns an API Gateway-style
response dict.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple
from metrics.registry import METRIC_REGISTRY
import json
from run_metrics import calculate_net_score
import boto3
from metrics.utils import fetch_hf_readme_text
from botocore.config import Config

lambda_client = boto3.client('lambda')

def run_all_metrics(event, context):
    """
    Triggered asynchronously from ArtifactHandler via Destination.
    The data from the first Lambda is found under:
      event["detail"]["responsePayload"]["body"]
    """
    print("Received event from ArtifactHandler:", json.dumps(event))

    try:
        # Step 1: Extract payload directly from the event (no EventBridge parsing needed!)
        data = event
        artifact_type = data.get("artifact_type")
        model_url = data.get("source_url")
        name = data.get("name")

        print(f"Processing artifact: {artifact_type} | URL: {model_url}")

        if not artifact_type or not model_url:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing artifact_type or source_url in direct payload."})
            }

    except Exception as e:
        # Handle unexpected errors during initial payload parsing
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal processing error: {str(e)}"})
        }

    results = {"Non-Model": "0.0"}
    net_score = 0.0

    if artifact_type == "model":

        readme_text = fetch_hf_readme_text(model_url)
        if readme_text is None:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to fetch README text."})
            }

        try:
            config = Config(
                read_timeout=15,
                connect_timeout=5,
                retries={
                    'max_attempts': 2
                }
            )


            bedrock = boto3.client("bedrock-runtime", region_name="us-east-2", config=config)

            prompt = f""" You are an expert analyst and trying to match HuggingFace models to their corresponding code and datasets.
        
            README:
            {readme_text}

            Task:
            - Identify from the README the url of the github code that is linked to this model.
            - Ensure the code url is valid. Attempt to return the url for the root directory.
            - Identify from the README the url of the dataset that is linked to this model
            - Respond in the following manner code_url, dataset_url
            - If you cannot find these things, return that string as NULL
            - Only respond with these things, and no other text. There is no need to label them either.
            """

            request_body = {
                'messages': [
                    {
                        'role': 'user',
                        'content': [{'text': prompt}]
                    }
                ],
                'inferenceConfig': {
                    'maxTokens': 256,
                    'temperature': 0.7
                }
            }

            response = bedrock.invoke_model(
                modelId='us.amazon.nova-2-lite-v1:0',
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            content_list = response_body["output"]["message"]["content"]
            # Extract the first text block
            text_block = next((item for item in content_list if "text" in item), None)
            if text_block is not None:
                urls = text_block["text"]
                urls = urls.split(",")
                code_url = urls[0]
                dataset_url = urls[1]
            

        except Exception as e:
            return "TIME OUT!"
            code_url = None
            dataset_url = None

        print(f"Code URL: {code_url}")
        print(f"Dataset URL: {dataset_url}")

        max_workers = 10
        
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(fn, model_url, code_url, dataset_url): key
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
        '''
        for k, (score, latency) in results.items():
            if score is None or score < 0.5:
                return {
                    "statusCode": 424,
                    "body": {}
                }
        '''
        
    output_payload = {
        "artifact_type": artifact_type,
        "model_url": model_url,
        "results": results,
        "net_score": net_score,
        "name": name
    }

    try:
        # The next function should also be called synchronously to ensure a final
        # 201/202 status can be returned from the API Gateway chain.
        ingestor_response = lambda_client.invoke(
            FunctionName="Upload",
            InvocationType='RequestResponse',
            Payload=json.dumps(output_payload)
        )
        
        # Check for errors from the Ingestor
        if 'FunctionError' in ingestor_response:
                # If the Ingestor failed, tell the client it was a server error
                error_payload = ingestor_response['Payload'].read().decode('utf-8')
                print(f"Ingestor failed: {error_payload}")
                return {
                "statusCode": 500,
                "body": json.dumps({"error": "Processing failed in the Ingestor service."})
            }
            
        # If Ingestor succeeded, assume it returns a clean API Gateway-compatible response
        # Read and parse the Ingestor's clean response
        ingestor_result_str = ingestor_response['Payload'].read().decode('utf-8')
        ingestor_result = json.loads(ingestor_result_str)

        # Return the Ingestor's statusCode and body back up the chain to the API client
        return ingestor_result
    
    except Exception as e:
        print(f"CRITICAL ERROR during synchronous Ingestor invocation: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal error during final step handoff."})
        }
    
