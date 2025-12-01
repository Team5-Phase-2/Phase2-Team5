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
import requests #NEW
import tempfile #NEW
import zipfile #NEW
from urllib.parse import urlparse #NEW
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

    #CHANGES START HERE---------------------------------------------

    download_url = None  

    try:
        #get url to download from
        parsed = urlparse(model_url)
        host = parsed.netloc.lower()

        #handle hugging face 
        if "huggingface.co" in host:
            
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) < 2:
                raise ValueError(f"Cannot infer Hugging Face repo from URL: {model_url}")
            hf_repo_id = "/".join(path_parts[:2])  

            api_url = f"https://huggingface.co/api/models/{hf_repo_id}"
            print(f"Fetching HF model metadata from {api_url}")
            info_resp = requests.get(api_url, timeout=(2.0, 8.0))
            info_resp.raise_for_status()
            info = info_resp.json() or {}

            head = info.get("sha")
            siblings = info.get("siblings") or []
            if not head or not isinstance(siblings, list) or not siblings:
                raise ValueError(f"No siblings or sha for HF model: {hf_repo_id}")

            zip_key = f"artifacts/{artifact_type}/{model_id}/artifact.zip"

            # Create a ZIP file in /tmp
            zip_path = f"/tmp/{model_id}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for s in siblings:
                    rfilename = (s.get("rfilename") or "").strip()
                    if not rfilename:
                        continue

                    file_url = f"https://huggingface.co/{hf_repo_id}/resolve/{head}/{rfilename}"
                    print(f"Downloading HF file: {file_url}")
                    r = requests.get(file_url, timeout=(2.0, 20.0))
                    r.raise_for_status()
                    zipf.writestr(rfilename, r.content)

            # Upload ZIP to S3
            with open(zip_path, "rb") as f:
                s3.put_object(
                    Bucket=s3_bucket,
                    Key=zip_key,
                    Body=f,
                    ContentType="application/zip",
                )

            #Generate presigned URL
            download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": s3_bucket, "Key": zip_key},
                ExpiresIn=3600,
            )

        #hanlde github
        elif "github.com" in host:

            #download repository archive as a ZIP
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) < 2:
                raise ValueError(f"Cannot infer GitHub repo from URL: {model_url}")

            owner, repo = path_parts[0], path_parts[1].replace(".git", "")
            
            zip_download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
            print(f"Downloading GitHub repo archive: {zip_download_url}")

            r = requests.get(zip_download_url, timeout=(5.0, 30.0))
            r.raise_for_status()

            zip_key = f"artifacts/{artifact_type}/{model_id}/artifact.zip"
            s3.put_object(
                Bucket=s3_bucket,
                Key=zip_key,
                Body=r.content,
                ContentType="application/zip",
            )

            #Generate presigned URL
            download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": s3_bucket, "Key": zip_key},
                ExpiresIn=3600,
            )

        #if neither of these print error
        else:
            # Unsupported domain – keep system working, just skip download_url.
            print(f"No artifact download implemented for URL host: {host}")

    except Exception as e:
        # Log the error but DO NOT fail upload entirely – we still want metadata/results stored.
        print(f"Artifact download/zip/upload failed: {e}")
        download_url = None
    
    #---------------------------------------------------------------

    # Construct the metadata payload that will be stored in S3.
    output = {
        "type": artifact_type,
        "model_url": model_url,
        "download_url": download_url, #THIS IS NEW
        "results": results,
        "net_score": net_score,
        "name": name,
        "id": model_id
    }

    metadata = {"name": name, "id": model_id, "type": artifact_type}
    data = {"url": model_url, "download_url": download_url} #THIS IS CHANGED

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
