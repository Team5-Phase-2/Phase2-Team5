import boto3
from moto import mock_aws
from backend.Reset.Reset import wipe_s3_bucket
import pytest

# Test using Moto
@mock_aws
def test_delete_all_files():
  # Create a mock S3 client and bucket
  s3 = boto3.client("s3", region_name="us-east-1")
  bucket_name = "dummy-bucket"
  s3.create_bucket(Bucket=bucket_name)

  # Upload dummy files
  keys = ["file1.txt", "file2.txt", "nested/file3.txt"]
  for key in keys:
    s3.put_object(Bucket=bucket_name, Key=key, Body=b"dummy data")

  # Verify they were created
  listed = s3.list_objects_v2(Bucket=bucket_name)
  assert "Contents" in listed
  assert len(listed["Contents"]) == 3

  # Call the function to delete all files
  wipe_s3_bucket(bucket_name)

  # Ensure the bucket is empty afterward
  listed_after = s3.list_objects_v2(Bucket=bucket_name)
  assert "Contents" not in listed_after or len(listed_after["Contents"]) == 0
