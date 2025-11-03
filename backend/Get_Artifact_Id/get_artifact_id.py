import json
import os
import boto3
from botocore.exceptions import ClientError


def get_artifact_handler(event, context):
    """
    Handles GET /artifact/{artifact_type}/{model_id}
    Triggered by API Gateway.
    On success, returns the stored artifact metadata from S3.
    """

    print("Received event:", json.dumps(event))

    # Get enviroment from s3
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})
        }

    s3 = boto3.client("s3")

    # Get artifact_type and model_id from path parameters 
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")
    model_id = path_params.get("id")

    if not artifact_type or not model_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing required parameters: artifact_type and model_id"})
        }

    # Construct the S3 key where this artifact should be stored ---
    s3_key = f"artifacts/{artifact_type}/{model_id}/metadata.json"

    # Try to fetch the object from S3 -
    try:
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        file_content = response["Body"].read().decode("utf-8")
        artifact_data = json.loads(file_content)
    except s3.exceptions.NoSuchKey:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Artifact with ID {model_id} not found."})
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Artifact with ID {model_id} not found."})
            }
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Error retrieving artifact", "detail": str(e)})
            }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Unhandled error", "detail": str(e)})
        }

    #get stuff from artifact 
    name = artifact_data.get("name")
    model_url = artifact_data.get("model_url")
    artifact_type = artifact_data.get("type")
    model_id = artifact_data.get("model_id")

    if not name or not model_url or not artifact_type or not model_id:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Malformed artifact record: missing one or more required fields"
            })
        }

    metadata = {
        "name": name,
        "id": model_id,
        "type": artifact_type
    }

    data = {
        "url": model_url
    }

    response_body = {
        "metadata": metadata,
        "data": data
    }


    # Return the artifact data
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response_body)
    }
