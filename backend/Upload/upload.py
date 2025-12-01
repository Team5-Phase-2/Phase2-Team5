"""backend.Upload.upload

Lambda function to accept artifact metadata and store it in S3.

The `lambda_handler` validates the incoming API Gateway payload, computes a
deterministic `model_id` based on the model name, writes metadata JSON to the
configured S3 bucket, and returns an API Gateway-compatible response.

Notes:
- Expects environment variable `REGISTRY_BUCKET` to be set to the S3 bucket
  name used for storing artifact metadata.
"""

import json
import os
import uuid
import hashlib
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """Handle POST /artifact/{artifact_type} requests.

    Args:
        event (dict): API Gateway event that includes a JSON body.
        context: Lambda context (unused).

    Returns:
        dict: API Gateway-compatible response with `statusCode` and `body`.
    """

    # Log the incoming event for debugging and traceability.
    print("Received event:", json.dumps(event))

    # Environment variable containing the target S3 bucket for artifact metadata
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        # Return 500 when the processing environment is misconfigured.
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})
        }

    # Initialize S3 client (uses execution role / environment credentials).
    s3 = boto3.client("s3")


    # Parse and validate JSON body from API Gateway event.
    body = event
    
    # Required fields expected from the upstream scorer/ingestor
    artifact_type = body.get("artifact_type")
    model_url = body.get("model_url")
    results = body.get("results")
    net_score = body.get("net_score")
    name = body.get("name")

    if not artifact_type or not model_url or results is None or net_score is None:
        # Missing required fields
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Missing one or more required fields: artifact_type, model_url, results, net_score"
            })
        }

    # Derive a human-friendly name from the URL (last path component).
    # name = model_url.rstrip("/").split("/")[-1]

    # Compute a deterministic numeric id using SHA-256; mod to keep it small.
    hash_object = hashlib.sha256(name.encode())
    numeric_hash = int(hash_object.hexdigest(), 16)
    model_id = numeric_hash % 9999999967

    

    # Construct the metadata payload that will be stored in S3.
    output = {
        "type": artifact_type,
        "model_url": model_url,
        "results": results,
        "net_score": net_score,
        "name": name,
        "id": model_id
    }

    metadata = {"name": name, "id": model_id, "type": artifact_type}
    data = {"url": model_url} #THIS IS CHANGED

    index_key = "name_id.txt"

    # Check if the index file exists
    try:
        s3.head_object(Bucket=s3_bucket, Key=index_key)
        file_exists = True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            file_exists = False
        else:
            raise

    # If missing, create empty file
    if not file_exists:
        s3.put_object(Bucket=s3_bucket, Key=index_key, Body=b"")

    # Prepare CSV line: name,id,type
    append_line = f"{name},{model_id},{artifact_type}\n".encode("utf-8")

    # Read existing contents
    try:
        obj = s3.get_object(Bucket=s3_bucket, Key=index_key)
        existing = obj["Body"].read()
    except ClientError:
        existing = b""  # file was empty / unreadable

    # Write updated file
    s3.put_object(
        Bucket=s3_bucket,
        Key=index_key,
        Body=existing + append_line
    )

    # Write metadata JSON to S3 under a predictable key.
    s3_key = f"artifacts/{artifact_type}/{model_id}/metadata.json"
    try:
        s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=json.dumps(output, indent=2), ContentType="application/json")
    except ClientError as e:
        # Surface S3 errors to the caller as a 500.
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to write to S3", "detail": str(e)})}

    # Return a successful 201 Created response including metadata and reference data.
    response_body = {"metadata": metadata, "data": data}
    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(response_body)
    }
