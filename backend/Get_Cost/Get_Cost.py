"""backend.Get_Cost.Get_Cost

Lambda function to retrieve the storage cost/size of an artifact.

Queries the S3 bucket for the artifact's zip file size and returns it in MB.
Handles GET /artifact/{artifact_type}/{id}/cost requests.
"""

import json
import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    Parameters:
      artifact_type* : [model, dataset, code]
      id* : string
      dependency: bool (false)
    Return:
      statusCode:
        200: Return cost (MB)
        400: Bad request format
        404: Artifact doesn't exist
        500: server error
      body:
        id : {
          "total cost" : float (size MB)
        }
    """

    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")  or {}
    id = path_params.get("id") or {}

    if not artifact_type or not id:
        return {
          "statusCode": 400,
          "body": json.dumps({"error": "Missing artifact_type or id"})
        }

    s3 = boto3.client("s3")
    s3_bucket = os.environ.get("REGISTRY_BUCKET")

    s3_key = f"artifacts/{artifact_type}/{id}/artifact.zip"

    try:
        s3_object = s3.head_object(Bucket=s3_bucket, Key= s3_key)
        total_cost_mb = round(s3_object["ContentLength"] / (1024 * 1024))
    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        # S3 returns "404", "NoSuchKey", or "NotFound" depending on API
        if error_code in ("404", "NoSuchKey", "NotFound"):
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Artifact registry file not found"})
            }

    # For now return a placeholder success response indicating sanitized input
    return {
        "statusCode": 200,
        "body": json.dumps({
            id: {
                "total_cost": total_cost_mb
            }
        }),
    }
