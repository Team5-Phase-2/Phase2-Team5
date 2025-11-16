import os
import json
import hashlib
import boto3
from moto import mock_aws
from backend.Artifacts.Artifacts import lambda_handler

BUCKET = "test-registry-bucket"

def _generate_artifact_id(name: str) -> str:
    return str(int(hashlib.sha256(name.encode()).hexdigest(), 16) % 9999999967)

# Helper to upload artifacts
def _upload_artifacts(s3, artifacts):
    for atype, name in artifacts.items():
        artifact_id = _generate_artifact_id(name)
        key = f"artifacts/{atype}/{artifact_id}/metadata.json"
        metadata = {"name": name, "id": artifact_id, "type": atype}
        s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(metadata))

@mock_aws
def test_list_all_artifacts():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})

    sample = {
        "model": "Test Model",
        "dataset": "Test Dataset",
        "code": "Test Code",
    }

    for atype, name in sample.items():
        artifact_id = _generate_artifact_id(name)
        key = f"artifacts/{atype}/{artifact_id}/metadata.json"
        metadata = {"name": name, "id": artifact_id, "type": atype}
        s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(metadata))

    event = {
        "body": json.dumps({"name": "*", "types": []}),
        "headers": {},
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    returned_names = {item["name"] for item in body}
    assert returned_names == set(sample.values())

@mock_aws
def test_filter_by_type_and_name():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})

    # Upload only one artifact for dataset
    artifact_id = _generate_artifact_id("Test Dataset")
    key = f"artifacts/dataset/{artifact_id}/metadata.json"
    metadata = {"name": "Test Dataset", "id": artifact_id, "type": "dataset"}
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(metadata))

    event = {
        "body": json.dumps({"name": "Test Dataset", "types": ["dataset"]}),
        "headers": {},
    }
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["name"] == "Test Dataset"
    assert body[0]["type"] == "dataset"


@mock_aws
def test_filter_multiple_types():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})

    artifacts = {"model": "Model A", "dataset": "Dataset A", "code": "Code A"}
    _upload_artifacts(s3, artifacts)

    event = {"body": json.dumps({"name": "*", "types": ["model", "dataset"]}), "headers": {}}
    response = lambda_handler(event, None)
    body = json.loads(response["body"])

    returned_types = {item["type"] for item in body}
    assert returned_types == {"model", "dataset"}

@mock_aws
def test_filter_type_excludes_unrelated():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})

    artifacts = {"model": "Model X", "dataset": "Dataset Y", "code": "Code Z"}
    _upload_artifacts(s3, artifacts)

    event = {"body": json.dumps({"name": "*", "types": ["code"]}), "headers": {}}
    response = lambda_handler(event, None)
    body = json.loads(response["body"])

    assert all(item["type"] == "code" for item in body)
    assert {item["name"] for item in body} == {"Code Z"}

# 6. Valid request but no artifacts found
@mock_aws
def test_no_artifacts_found():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "us-east-2"})

    # Do NOT upload any artifacts
    event = {"body": json.dumps({"name": "*", "types": ["model", "dataset"]}), "headers": {}}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert isinstance(body, list)
    assert len(body) == 0

# 1. Missing REGISTRY_BUCKET environment variable
@mock_aws
def test_missing_env_var():
    os.environ["REGISTRY_BUCKET"] = ""
    event = {"body": json.dumps({"name": "*", "types": ["model"]}), "headers": {}}
    # Do NOT set REGISTRY_BUCKET
    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    assert "REGISTRY_BUCKET" in response["body"] or "missing" in response["body"].lower()
    os.environ["REGISTRY_BUCKET"] = BUCKET

# 2. Invalid JSON in request body
@mock_aws
def test_invalid_json_body():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    event = {"body": "{invalid-json}", "headers": {}}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    assert "Invalid JSON" in response["body"] or "error" in response["body"].lower()

# 3. Invalid name field (empty string)
@mock_aws
def test_invalid_name_empty():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    event = {"body": json.dumps({"name": "", "types": ["model"]}), "headers": {}}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    assert "name" in response["body"].lower()

# 4. Invalid types field (not a list)
@mock_aws
def test_invalid_types_not_list():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    event = {"body": json.dumps({"name": "*", "types": "model"}), "headers": {}}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    assert "types" in response["body"].lower()

# 5. Invalid type values
@mock_aws
def test_invalid_type_values():
    os.environ["REGISTRY_BUCKET"] = BUCKET
    event = {"body": json.dumps({"name": "*", "types": ["invalid_type"]}), "headers": {}}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    assert "invalid" in response["body"].lower()
