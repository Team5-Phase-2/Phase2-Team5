"""Unit tests for the Reset Lambda function.

Tests S3 bucket wiping and cleanup operations.
"""

import os
import boto3
from moto import mock_aws
from backend.Reset.Reset import wipe_s3_bucket

@mock_aws
def test_delete_all_files():
    # Set the environment variable for the bucket
    bucket_name = "dummy-bucket"
    os.environ["REGISTRY_BUCKET"] = bucket_name

    # Create a mock S3 client and bucket
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "us-east-2"}
    )


    # Upload dummy files
    keys = ["file1.txt", "file2.txt", "nested/file3.txt"]
    for key in keys:
        s3.put_object(Bucket=bucket_name, Key=key, Body=b"dummy data")

    # Verify they were created
    listed = s3.list_objects_v2(Bucket=bucket_name)
    assert "Contents" in listed
    assert len(listed["Contents"]) == 3

    # Call the function to delete all files
    wipe_s3_bucket(None, None)  # No arguments needed

    # Ensure the bucket is empty afterward
    listed_after = s3.list_objects_v2(Bucket=bucket_name)
    contents = listed_after.get("Contents", [])
    assert len(contents) == 0, f"Bucket is not empty, still has {len(contents)} objects"
