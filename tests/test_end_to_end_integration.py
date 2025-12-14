# tests/test_end_to_end_integration.py

"Full End to End Integration Tests of the Systems"
"Test for both huggingface and github links "
"Test for model and code"

import sys
import os

# Ensure backend/Rate is on the import path (matches legacy test behavior)
RATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "Rate"))
if RATE_DIR not in sys.path:
    sys.path.insert(0, RATE_DIR)


import json
import os
import boto3
import pytest
from moto import mock_aws
from unittest.mock import MagicMock

from backend.Rate.metric_runner import run_all_metrics
from backend.Get_Rate.Get_Rate import lambda_handler as get_rate_handler
from backend.Delete.delete import delete_artifact
from backend.Reset.Reset import wipe_s3_bucket
from backend.Upload.upload import lambda_handler as upload_handler


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")


@pytest.fixture
def mock_s3_bucket(aws_env):
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-2")
        s3.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
        )
        yield s3


@pytest.fixture
def mock_metrics(monkeypatch):
    from backend.Rate.metric_runner import METRIC_REGISTRY

    mocked_return = (0.9, 1)  # always passing

    monkeypatch.setattr(
        "backend.Rate.metric_runner.METRIC_REGISTRY",
        [(key, (lambda *args, ret=mocked_return: ret)) for key, _ in METRIC_REGISTRY],
    )


@pytest.fixture
def mock_lambda_invoke(monkeypatch):
    def fake_invoke(FunctionName, InvocationType, Payload):
        payload = json.loads(Payload)
        response = upload_handler(payload, None)
        return {
            "Payload": MagicMock(read=lambda: json.dumps(response).encode())
        }

    fake_lambda_client = MagicMock()
    fake_lambda_client.invoke.side_effect = fake_invoke

    # Patch the already-imported client inside metric_runner
    monkeypatch.setattr(
        "backend.Rate.metric_runner.lambda_client",
        fake_lambda_client,
    )


@pytest.fixture
def mock_utils(monkeypatch):
    monkeypatch.setattr(
        "backend.Rate.metric_runner.fetch_hf_readme_text",
        lambda _: "Mock README"
    )

@pytest.fixture
def mock_ssm(monkeypatch):
    fake_ssm = MagicMock()
    fake_ssm.send_command.return_value = {"Command": {"CommandId": "test"}}

    real_boto3_client = boto3.client  # keep original before patching

    def fake_client(service, **kwargs):
        if service == "ssm":
            return fake_ssm
        return real_boto3_client(service, **kwargs)  # call original, not patched

    monkeypatch.setattr(boto3, "client", fake_client)

    monkeypatch.setenv("EC2_ID", "i-test123")
    monkeypatch.setenv("DOWNLOAD_SCRIPT_PATH", "/tmp/fake_script.py")

def copy_code_metadata_to_model(s3, bucket, artifact_id):
    src_key = f"artifacts/code/{artifact_id}/metadata.json"
    dst_key = f"artifacts/model/{artifact_id}/metadata.json"

    obj = s3.get_object(Bucket=bucket, Key=src_key)
    s3.put_object(
        Bucket=bucket,
        Key=dst_key,
        Body=obj["Body"].read(),
        ContentType="application/json",
    )

def test_full_end_to_end_pipeline(
    mock_s3_bucket,
    mock_metrics,
    mock_lambda_invoke,
    mock_utils,
    mock_ssm,
):
    # ------------------ 1. RUN METRICS ------------------
    event = {
        "artifact_type": "model",
        "source_url": "https://huggingface.co/test/model",
        "name": "test-model"
    }

    response = run_all_metrics(event, None)
    assert response["statusCode"] == 201

    body = json.loads(response["body"])
    model_id = body["metadata"]["id"]

    # ------------------ 2. GET RATE ------------------
    rate_event = {"pathParameters": {"id": model_id}}
    rate_response = get_rate_handler(rate_event, None)

    assert rate_response["statusCode"] == 200
    rate_body = json.loads(rate_response["body"])
    assert rate_body["name"] == "test-model"
    assert "net_score" in rate_body

    # ------------------ 3. DELETE ARTIFACT ------------------
    delete_event = {
        "pathParameters": {
            "artifact_type": "model",
            "id": model_id
        }
    }

    delete_resp = delete_artifact(delete_event, None)
    assert delete_resp["statusCode"] == 200

    # ------------------ 4. RESET BUCKET ------------------
    reset_resp = wipe_s3_bucket({}, None)
    assert reset_resp["statusCode"] == 200


def test_full_end_to_end_pipeline_code_artifact(
    mock_s3_bucket,
    mock_metrics,
    mock_lambda_invoke,
    mock_utils,
    mock_ssm,
):
    # ------------------ 1. RUN METRICS ------------------
    event = {
        "artifact_type": "code",
        "source_url": "https://github.com/test-user/test-repo",
        "name": "test-code-repo"
    }

    response = run_all_metrics(event, None)
    assert response["statusCode"] == 201

    body = json.loads(response["body"])
    artifact_id = body["metadata"]["id"]

    # ------------------ 2. GET RATE ------------------
    # Copy code artifact metadata to model path so Get_Rate can read it
    copy_code_metadata_to_model(
        mock_s3_bucket,
        "test-bucket",
        artifact_id,
    )

    rate_event = {"pathParameters": {"id": artifact_id}}
    rate_response = get_rate_handler(rate_event, None)

    assert rate_response["statusCode"] == 200
    rate_body = json.loads(rate_response["body"])
    assert rate_body["name"] == "test-code-repo"
    assert "net_score" in rate_body

    # ------------------ 3. DELETE ARTIFACT ------------------
    delete_event = {
        "pathParameters": {
            "artifact_type": "code",
            "id": artifact_id
        }
    }

    delete_resp = delete_artifact(delete_event, None)
    assert delete_resp["statusCode"] == 200

    # ------------------ 4. RESET BUCKET ------------------
    reset_resp = wipe_s3_bucket({}, None)
    assert reset_resp["statusCode"] == 200


