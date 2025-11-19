import json
import os
import hashlib
import boto3
import re


def lambda_handler(event, context):
  """
  Handle GET requests for the /artifact/model/{id}/rate endpoint.
  This AWS Lambda handler expects an API Gateway event containing a path of the
  form "/artifact/model/{model_id}/rate".
  - Returns:
      - 200 with Content-Type "application/json" and the serialized response body
        on success.
      - 404 with an error JSON body when the metadata file cannot be retrieved from S3.
      - 500 with an error JSON body when REGISTRY_BUCKET is not configured.
  Notes and edge-cases:
  - The handler treats missing or malformed metric entries defensively by
    returning 0 for absent scores/latencies.
  - The function assumes the event path structure is valid; malformed paths may
    cause IndexError. Consider validating path segments before indexing.
  - Any S3 errors are surfaced in the 404 response body; you may want to map
    specific exceptions (e.g., NoSuchKey vs permission errors) to more
    appropriate HTTP status codes.
  - To improve security and robustness: validate model_id contents, limit error
    details returned to clients, and add structured logging for observability.
  """

  path = event["path"]
  parts = path.strip("/").split("/")
  model_id = parts[2]

  # use the extracted model id as the S3 key (adjust prefix if needed)
  s3 = boto3.client("s3")
  s3_bucket = os.environ.get("REGISTRY_BUCKET")
  if not s3_bucket:
    return {"statusCode": 500, "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})}

  s3_key = f"artifacts/model/{model_id}/metadata.json"

  try:
    response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
  except Exception as e:
    return {"statusCode": 404, "body": json.dumps({"error": f"Metadata not found: {e}"})}

  file_content = response["Body"].read().decode("utf-8")
  data = json.loads(file_content)
  # The stored metadata (from Upload) contains at least:
  #  name, type (or category), model_url, results (mapping metric->[score, latency]), net_score
  name = data.get("name")
  model_url = data.get("model_url")
  results = data.get("results")
  net_score = data.get("net_score")

  def get_score(m):
    v = results.get(m)
    if isinstance(v, (list, tuple)) and len(v) >= 1:
      return v[0] if v[0] is not None else 0
    return v if isinstance(v, (int, float)) else 0


  def get_latency(m):
    v = results.get(m)
    if isinstance(v, (list, tuple)) and len(v) >= 2:
      return v[1] if v[1] is not None else 0
    return 0

  response_obj = {
    "name": name,
    "category": "model",
    "net_score": net_score,
    "net_score_latency": 0,
    "ramp_up_time": get_score("ramp_up_time"),
    "ramp_up_time_latency": get_latency("ramp_up_time"),
    "bus_factor": get_score("bus_factor"),
    "bus_factor_latency": get_latency("bus_factor"),
    "performance_claims": get_score("performance_claims"),
    "performance_claims_latency": get_latency("performance_claims"),
    "license": get_score("license"),
    "license_latency": get_latency("license"),
    "dataset_and_code_score": get_score("dataset_and_code_score"),
    "dataset_and_code_score_latency": get_latency("dataset_and_code_score"),
    "dataset_quality": get_score("dataset_quality"),
    "dataset_quality_latency": get_latency("dataset_quality"),
    "code_quality": get_score("code_quality"),
    "code_quality_latency": get_latency("code_quality"),
    "reproducibility": 0,
    "reproducibility_latency": 0,
    "reviewedness": 0,
    "reviewedness_latency": 0,
    "tree_score": 0,
    "tree_score_latency": 0,
    "size_score": {
      "raspberry_pi": 0,
      "jetson_nano": 0,
      "desktop_pc": 0,
      "aws_server": 0,
    },
    "size_score_latency": get_latency("size_score"),
  }

  # Return the reformatted object
  return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(response_obj)}



