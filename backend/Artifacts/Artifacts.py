"""backend.Artifacts.Artifacts

AWS Lambda function to list and retrieve artifact metadata from S3.

Provides a lambda_handler that accepts requests to list artifacts by type,
with pagination support via offset headers.
"""

import hashlib
import json
import os
import boto3


def lambda_handler(event, context):
    """AWS Lambda handler to list artifact metadata stored in S3.

    The handler expects an event with an optional JSON body containing:
      - name: str (currently unused; kept for compatibility)
      - types: List[str]

    Pagination is controlled by an "offset" header.
    """

    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {
          "statusCode": 500,
          "body": json.dumps({"error": "REGISTRY_BUCKET not configured"}),
        }

    try:
        body = json.loads(event.get("body", "[]"))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    # Expecting an array from the client
    if not isinstance(body, list) or len(body) == 0:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Request body must be a non-empty array"})
        }

    item = body[0]

    name = item.get("name")
    types = item.get("types")

    # Validate
    if not isinstance(name, str) or name.strip() == "":
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid 'name'; must be a non-empty string."})
        }

    if not isinstance(types, list):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "'types' must be an array."})
        }

    valid_types = {"model", "dataset", "code"}

    if any(t not in valid_types for t in item["types"]):
        return {"statusCode": 400, "body": json.dumps({"error": "invalid type value"})}

    # Handle pagination offset
    try:
        offset = int(event.get("headers", {}).get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    limit = 50  # Fixed page size

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    response_objects = []

    if types == []:
        types = ["model", "dataset", "code"]

    for artifact_type in types:
        prefix = f"artifacts/{artifact_type}"

        if name != "*":
            # Pulled from upload.py
            hash_object = hashlib.sha256(name.encode())
            numeric_hash = int(hash_object.hexdigest(), 16)
            model_id = numeric_hash % 9999999967
            key = f"{prefix}/{model_id}/metadata.json"
            print(f"lambda_handler: looking up key={key}")

            meta = extract_metadata(s3, s3_bucket, key)
            if meta:
                response_objects.append(meta)
            continue

        for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj.get("Key")
                    if not key:
                        continue
                    if key.endswith("metadata.json"):
                        meta = extract_metadata(s3, s3_bucket, key)
                        if meta:
                            response_objects.append(meta)

    # Apply pagination
    paginated_objects = response_objects[offset: offset + limit]
    next_offset = offset + limit if len(response_objects) > offset + limit else None

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    if next_offset:
        headers["offset"] = str(next_offset)

    return {"statusCode": 200, "headers": headers, "body": json.dumps(paginated_objects)}


def extract_metadata(s3, s3_bucket: str, key: str):
    """Extract the metadata for a given object based on the filepath

    Returns an object listing the name, id, and type of the artifact for
    the given key.
    """
    try:
        metadata_obj = s3.get_object(Bucket=s3_bucket, Key=key)
    except Exception as e:
        print(f"extract_metadata: failed to get object {key}: {e}")
        return

    body = metadata_obj.get("Body")
    raw = body.read() if body is not None else b""
    # S3 returns bytes; decode if necessary
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            raw = raw.decode("latin-1", errors="ignore")
    try:
        metadata = json.loads(raw)
    except Exception:
        # Skip malformed metadata files
        print(f"extract_metadata: failed to parse metadata for key={key}")
        return

    ret = {
        "name": metadata.get("name"),
        "id": metadata.get("id"),
        "type": metadata.get("type"),
    }

    print(f"extract_metadata: Found {ret}")
    return ret
