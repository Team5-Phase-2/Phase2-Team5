import os
import json

import boto3
import pytest
from moto import mock_aws

from backend.Get_Rate.Get_Rate import lambda_handler

@mock_aws
def test_missing_metadata_returns_404():
    # Create mock bucket but do not upload metadata
    bucket = "test-bucket"
    os.environ["REGISTRY_BUCKET"] = bucket
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)

    event = {"pathParameters": {"id": "99999"}}

    resp = lambda_handler(event, None)
    assert resp.get("statusCode") == 404
    body = json.loads(resp.get("body"))
    assert "Metadata not found" in body.get("error", "")


@mock_aws
def test_successful_return_200_and_schema():
    bucket = "test-bucket"
    os.environ["REGISTRY_BUCKET"] = bucket
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=bucket)

    # Create a metadata object with results mapping
    model_id = "424242"
    key = f"artifacts/model/{model_id}/metadata.json"
    metadata = {
        "name": "example-model",
        "model_url": "https://huggingface.co/owner/example-model",
        "results": {
            "ramp_up_time": [0.8, 120],
            "bus_factor": [0.5, 30],
            "performance_claims": [0.6, 200],
            "license": [1.0, 10],
            "dataset_and_code_score": [0.7, 50],
            "dataset_quality": [0.6, 40],
            "code_quality": [0.65, 60],
            "tree_score": [0.4, 20],
            "size_score": [0.9, 5]
        },
        "net_score": 0.7,
    }
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(metadata).encode("utf-8"))

    event = {"pathParameters": {"id": model_id}}
    
    resp = lambda_handler(event, None)
    assert resp.get("statusCode") == 200
    body = json.loads(resp.get("body"))

    # Check top-level fields from the expected schema
    expected_keys = {
        "name",
        "category",
        "net_score",
        "net_score_latency",
        "ramp_up_time",
        "ramp_up_time_latency",
        "bus_factor",
        "bus_factor_latency",
        "performance_claims",
        "performance_claims_latency",
        "license",
        "license_latency",
        "dataset_and_code_score",
        "dataset_and_code_score_latency",
        "dataset_quality",
        "dataset_quality_latency",
        "code_quality",
        "code_quality_latency",
        "tree_score",
        "tree_score_latency",
        "size_score",
        "size_score_latency",
    }

    print(body)

    assert expected_keys.issubset(set(body.keys()))
    # Check some values are taken from metadata
    assert body["name"] == metadata["name"]
    assert body["net_score"] == metadata["net_score"]
    assert body["ramp_up_time"] == pytest.approx(0.8)
    assert body["ramp_up_time_latency"] == 120

