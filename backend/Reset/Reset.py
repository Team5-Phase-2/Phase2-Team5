from boto3 import client
from os import environ

def wipe_s3_bucket(event, context):
  """Delete all objects from an S3 bucket (paginated + batch-safe)."""
  s3_client = client("s3", region_name='us-east-2')

  s3_bucket = environ.get("REGISTRY_BUCKET")
  if not s3_bucket:
    return {
      "statusCode": 500,
      "body": "REGISTRY_BUCKET environment variable is not set."
    }

  try:
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=s3_bucket)

    for page in pages:
      if "Contents" not in page:
        continue

      # Delete in batches of 1000
      objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
      for i in range(0, len(objects), 1000):
        batch = objects[i:i + 1000]
        s3_client.delete_objects(
          Bucket=s3_bucket,
          Delete={"Objects": batch}
        )
  except Exception as e:
    return {
      "statusCode": 500,
      "body": "{e}"
    }

  return {
    "statusCode": 200
  }

