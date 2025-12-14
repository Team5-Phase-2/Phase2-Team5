"""backend.Delete.delete

Utilities to delete an id specified S3 route by deleting all stored objects.

This module provides a single helper `delete_artifact(event, context)` which
uses S3 paginators and batched deletes to remove objects safely. Intended for
administrative/testing use only.
"""

from os import environ
import json
from boto3 import client

def delete_artifact(event, context):
    """Delete all objects from a specified artifact.

    The function reads the `REGISTRY_BUCKET` environment variable to determine
    the target bucket. Objects are listed using a paginator and deleted in
    batches to stay within API limits.
    """

    path_params = event.get("pathParameters") or {}
    id = path_params.get("id") or {}
    artifact_type = path_params.get("artifact_type")

    if not id or not artifact_type:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing path parameter 'id' or 'artifact_type'"})
        }

    # Create an S3 client; region can be overridden in the environment/role.
    s3_client = client("s3", region_name='us-east-2')

    s3_bucket = environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {"statusCode": 500, "body": "REGISTRY_BUCKET environment variable is not set."}

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=s3_bucket, Prefix= f"artifacts/{artifact_type}/{id}/" )

        id_exists = False
        for page in pages:
            if "Contents" in page:
                id_exists = True

                # Create batch for deletion
                objects_to_delete = [{"Key": obj["Key"]} for obj in page["Contents"]]

                if objects_to_delete:
                    s3_client.delete_objects(
                        Bucket=s3_bucket,
                        Delete={"Objects": objects_to_delete}
                    )
        if not id_exists:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Artifact with id '{id}' and type '{artifact_type}' not found."})
            }
    except Exception as e:
        # Return error information for observability; do not leak secrets.
        return {"statusCode": 500, "body": str(e)}

    return {"statusCode": 200}
