"""backend.Reset.Reset

Utilities to reset the registry S3 bucket by deleting all stored objects.

This module provides a single helper `wipe_s3_bucket(event, context)` which
uses S3 paginators and batched deletes to remove objects safely. Intended for
administrative/testing use only.
"""

from boto3 import client
from os import environ


def wipe_s3_bucket(event, context):
    """Delete all objects from a configured S3 bucket.

    The function reads the `REGISTRY_BUCKET` environment variable to determine
    the target bucket. Objects are listed using a paginator and deleted in
    batches to stay within API limits.
    """

    # Create an S3 client; region can be overridden in the environment/role.
    s3_client = client("s3", region_name='us-east-2')

    s3_bucket = environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {"statusCode": 500, "body": "REGISTRY_BUCKET environment variable is not set."}

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=s3_bucket)

        for page in pages:
            # If the page contains no objects, skip it.
            if "Contents" not in page:
                continue

            # Build delete payloads and delete in chunks of up to 1000 keys.
            objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
            for i in range(0, len(objects), 1000):
                batch = objects[i:i + 1000]
                s3_client.delete_objects(Bucket=s3_bucket, Delete={"Objects": batch})
    except Exception as e:
        # Return error information for observability; do not leak secrets.
        return {"statusCode": 500, "body": str(e)}

    return {"statusCode": 200}

