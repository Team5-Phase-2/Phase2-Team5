"""backend.Upload.upload

Lambda function to accept artifact metadata and store it in S3.

The `lambda_handler` validates the incoming API Gateway payload, computes a
deterministic `model_id` based on the model name, writes metadata JSON to the
configured S3 bucket, and returns an API Gateway-compatible response.

Notes:
- Expects environment variable `REGISTRY_BUCKET` to be set to the S3 bucket
  name used for storing artifact metadata.
"""
import os
import json
import zipfile
import io
import hashlib
import base64
from urllib.parse import urlparse
import requests
from botocore.exceptions import ClientError
import boto3

os.makedirs("/tmp/huggingface/hub", exist_ok=True)

def lambda_handler(event, context):
    """Handle POST /artifact/{artifact_type} requests.

    Args:
        event (dict): API Gateway event that includes a JSON body.
        context: Lambda context (unused).

    Returns:
        dict: API Gateway-compatible response with `statusCode` and `body`.
    """

    # Environment variable containing the target S3 bucket for artifact metadata
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        # Return 500 when the processing environment is misconfigured.
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})
        }

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

    # URLs to store
    zip_download_url = None

    parsed = urlparse(model_url)
    host = parsed.netloc.lower()

    # =====================================================================
    # 1. FIRE OFF EC2 FULL DOWNLOAD
    # =====================================================================
    
    ssm = boto3.client("ssm")
    EC2_ID = os.environ.get("EC2_ID")
    SCRIPT_PATH = os.environ.get("DOWNLOAD_SCRIPT_PATH")

    ssm.send_command(
        InstanceIds=[EC2_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={
            "commands": [
                f"python3 {SCRIPT_PATH} --url {model_url} --artifact_id {model_id} --artifact_type {artifact_type}"
            ]
        }
    )
    

    # =====================================================================
    # 2. CREATE PLACEHOLDER S3 OBJECT FOR DOWNLOAD URL GENERATION
    # =====================================================================
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        pass  # No files added → valid empty ZIP
    buf.seek(0)

    zip_key = f"artifacts/{artifact_type}/{model_id}/artifact.zip"
    s3.put_object(
        Bucket=s3_bucket,
        Key=zip_key,
        Body=buf.getvalue(),
        ContentType="application/zip"
    )

    zip_download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": s3_bucket, "Key": zip_key},
        ExpiresIn=604799 ,
    )

    # =====================================================================
    # 3. README-ONLY DOWNLOAD
    # =====================================================================
    path_parts = [p for p in parsed.path.split("/") if p]
    try:
        # -------------------- GitHub README --------------------
        if "github.com" in host:
            owner, repo = path_parts[0], path_parts[1].replace(".git", "")
            api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
            print("GITHUB README:", api_url)

            github_resp = requests.get(api_url, timeout=(3, 12), headers={"User-Agent": "Mozilla/5.0"})
            github_resp.raise_for_status()

            info = github_resp.json()
            readme_bytes = base64.b64decode(info["content"])
            readme_name = info.get("name", "README")

            readme_key = f"artifacts/{artifact_type}/{model_id}/{readme_name}"
            s3.put_object(
                Bucket=s3_bucket,
                Key=readme_key,
                Body=readme_bytes,
                ContentType="text/plain"
            )

        # -------------------- HuggingFace README --------------------
        elif "huggingface.co" in host:
            
            path = parsed.path.strip("/")
            parts = path.split("/")

            if parts[0] == "datasets":
                repo_type = "datasets"
                repo_id = "/".join(parts[1:3])   # owner/name
            else:
                repo_type = "models"
                repo_id = "/".join(parts[0:2])   # owner/name

            api_url = f"https://huggingface.co/api/{repo_type}/{repo_id}"
            print("HF README API:", api_url)

            huggingface_resp = requests.get(api_url, timeout=(3, 12), headers={"User-Agent": "Mozilla/5.0"}).json()
            sha = huggingface_resp.get("sha")
            siblings = huggingface_resp.get("siblings", [])

            readme_file = None
            for s in siblings:
                if "readme" in s.get("rfilename", "").lower():
                    readme_file = s["rfilename"]
                    break

            if readme_file:
                raw_url = f"https://huggingface.co/{repo_id}/resolve/{sha}/{readme_file}"
                r = requests.get(raw_url, timeout=(3, 12), headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()

                readme_key = f"artifacts/{artifact_type}/{model_id}/{readme_file}"
                s3.put_object(
                    Bucket=s3_bucket,
                    Key=readme_key,
                    Body=r.content,
                    ContentType="text/plain"
                )
    except Exception as e:
        readme_key = None
    # =====================================================================
    # 4. FORMAT METADATA AND STORE IN S3
    # =====================================================================

    #if no zip download url found then return model url
    if zip_download_url is None:
        zip_download_url = model_url


    # Construct the metadata payload that will be stored in S3.
    # Note: not currently using readme url but have it if needed later
    output = {
        "type": artifact_type,
        "model_url": model_url,
        "download_url": zip_download_url, #THIS IS NEW
        "results": results,
        "net_score": net_score,
        "name": name,
        "id": model_id
    }

    metadata = {"name": name, "id": model_id, "type": artifact_type}
    data = {"url": model_url, "download_url": zip_download_url} #THIS IS CHANGED

    #Name tracking for READMEs here-------------------------------------
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
    #--------------------------------------------------------------------

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
