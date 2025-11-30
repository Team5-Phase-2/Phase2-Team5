"""backend.Get_Artifact_Id.get_artifact_id

Lambda handler used to retrieve previously stored artifact metadata from S3.

Expects path parameters `artifact_type` and `id` (model id). Returns the JSON
metadata object stored during ingestion. This is a thin wrapper around S3
`get_object` with API Gateway-compatible error handling.
"""

import json
import os
import boto3
from botocore.exceptions import ClientError


def get_artifact_handler(event, context):
    """Retrieve artifact metadata from the registry S3 bucket.
        Handles GET /artifact/{artifact_type}/{model_id}

    Args:
        event (dict): API Gateway event with `pathParameters` containing
            `artifact_type` and `id`.
        context: Lambda context object (unused).

    Returns:
        dict: API Gateway response with `statusCode` and `body`.
    """

    print("Received event:", json.dumps(event))

    # Read configured registry bucket
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {"statusCode": 500, "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})}

    s3 = boto3.client("s3")

    # Extract parameters from the incoming request
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")
    model_id = path_params.get("id")

    #if not artifact_type or not model_id:
    if not artifact_type or model_id is None: #THIS LINE MODIFIED
        return {"statusCode": 400, "body": json.dumps({"error": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."})}

    # Build the S3 key where metadata is stored
    s3_key = f"artifacts/{artifact_type}/{model_id}/metadata.json"

    # Try to fetch the object from S3 -
    try:
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        file_content = response["Body"].read().decode("utf-8")
        artifact_data = json.loads(file_content)
    except s3.exceptions.NoSuchKey:
        return {"statusCode": 404, "body": json.dumps({"error": f"Artifact does not exist."})}
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {"statusCode": 404, "body": json.dumps({"error": f"Artifact does not exist."})}
        else:
            return {"statusCode": 400, "body": json.dumps({"error": "Error retrieving artifact", "detail": str(e)})}
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": "Unhandled error", "detail": str(e)})}

    # Validate required fields exist in the stored artifact
    '''
    name = artifact_data.get("name")
    model_url = artifact_data.get("model_url")
    artifact_type = artifact_data.get("type")
    model_id = artifact_data.get("id")

    if not name or not model_url or not artifact_type or not model_id:
        return {"statusCode": 400, "body": json.dumps({"error": "Malformed artifact record: missing one or more required fields"})}

    metadata = {"name": name, "id": model_id, "type": artifact_type}
    data = {"url": model_url}
    response_body = {"metadata": metadata, "data": data}

    return {"statusCode": 200, "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}, "body": json.dumps(response_body)}
    '''

    metadata = {
        "name": artifact_data.get("name"),
        "id": artifact_data.get("id"),
        "type": artifact_data.get("type")
    }

    data = {
        "url": artifact_data.get("model_url")
    }

    if (
        metadata["name"] is None or
        metadata["id"] is None or
        metadata["type"] is None or
        data["url"] is None
    ):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Malformed artifact record: missing one or more required fields"})
        }

    response_body = {
        "metadata": metadata,
        "data": data
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response_body)
    }
