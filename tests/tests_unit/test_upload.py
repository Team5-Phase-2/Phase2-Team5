"""Unit tests for the Upload Lambda function.

Tests artifact upload to S3, presigned URL generation, and AWS service interactions
with mocked boto3 clients. Validates error handling for missing configuration and fields.
"""

import json
import pytest
from unittest.mock import MagicMock
import backend.Upload.upload as up
from botocore.exceptions import ClientError


@pytest.fixture
def mock_env(monkeypatch):
    """Set up required environment variables for upload tests."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")
    monkeypatch.setenv("EC2_ID", "i-123456")
    monkeypatch.setenv("DOWNLOAD_SCRIPT_PATH", "/fake/script.py")


@pytest.fixture
def mock_boto(monkeypatch):
    """Mock S3 and SSM services for upload tests."""
    s3 = MagicMock()
    ssm = MagicMock()

    # ---- S3 behavior ----
    s3.generate_presigned_url.return_value = "https://signed-url"
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"")}
    s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )

    def client(name, *args, **kwargs):
        if name == "s3":
            return s3
        if name == "ssm":
            return ssm
        raise ValueError(name)

    monkeypatch.setattr(up.boto3, "client", client)

    return s3, ssm


@pytest.fixture
def base_event():
    """Create a valid base API event for upload tests."""
    return {
        "artifact_type": "model",
        "model_url": "https://github.com/owner/repo",
        "results": {"metric": 1},
        "net_score": 0.9,
        "name": "test-model",
    }


def test_missing_registry_bucket(monkeypatch, base_event):
    """Verify that missing REGISTRY_BUCKET environment variable returns 500 error"""
    monkeypatch.delenv("REGISTRY_BUCKET", raising=False)

    resp = up.lambda_handler(base_event, None)

    assert resp["statusCode"] == 500
    assert "REGISTRY_BUCKET" in resp["body"]


def test_missing_required_fields(mock_env):
    """Verify that missing required fields in event returns 400 error"""
    resp = up.lambda_handler({}, None)

    assert resp["statusCode"] == 400
    assert "Missing one or more required fields" in resp["body"]


def test_successful_github_upload(mock_env, mock_boto, base_event, monkeypatch):
    """Verify successful artifact upload from GitHub returns 200 status"""
    s3, ssm = mock_boto

    # Mock GitHub README call to fail safely
    monkeypatch.setattr(up.requests, "get", lambda *a, **k: MagicMock(
        raise_for_status=lambda: (_ for _ in ()).throw(RuntimeError("fail"))
    ))

    resp = up.lambda_handler(base_event, None)

    assert resp["statusCode"] == 201

    body = json.loads(resp["body"])
    assert body["metadata"]["type"] == "model"
    assert body["metadata"]["name"] == "test-model"
    assert "download_url" in body["data"]

    # SSM command fired
    ssm.send_command.assert_called_once()

    # Metadata written
    assert s3.put_object.call_count >= 2


def test_successful_huggingface_upload(mock_env, mock_boto, base_event, monkeypatch):
    base_event["model_url"] = "https://huggingface.co/owner/repo"

    def fake_get(url, *a, **k):
        if "api/models" in url:
            return MagicMock(json=lambda: {
                "sha": "abc",
                "siblings": [{"rfilename": "README.md"}],
            })
        return MagicMock(
            content=b"README",
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(up.requests, "get", fake_get)

    resp = up.lambda_handler(base_event, None)

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["metadata"]["type"] == "model"


def test_s3_metadata_write_failure_returns_500(mock_env, mock_boto, base_event):
    s3, _ = mock_boto

    def selective_put_object(**kwargs):
        if kwargs.get("Key", "").endswith("metadata.json"):
            raise ClientError(
                {"Error": {"Code": "500"}}, "PutObject"
            )
        return {}

    s3.put_object.side_effect = selective_put_object

    resp = up.lambda_handler(base_event, None)

    assert resp["statusCode"] == 500
    assert "Failed to write to S3" in resp["body"]
