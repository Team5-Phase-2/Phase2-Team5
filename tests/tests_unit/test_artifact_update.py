"""Unit tests for the Artifact Update Lambda function.
Tests artifact metadata updates, validation, and error handling for various
input scenarios including missing fields, type mismatches, and service failures.
"""

import json
import io
import pytest
from unittest.mock import MagicMock

from backend.Update import update

class FakePayload:
    """Simulates the streaming Payload object returned by Lambda.invoke"""
    def __init__(self, data):
        self._data = data

    def read(self):
        return json.dumps(self._data).encode("utf-8")


def make_event(
    *,
    path_type="model",
    path_id="123",
    body_type="model",
    body_id="123",
    name="example-model",
):
    """Create a valid API Gateway event with overridable fields"""
    return {
        "pathParameters": {
            "artifact_type": path_type,
            "id": path_id,
        },
        "body": json.dumps({
            "metadata": {
                "name": name,
                "id": body_id,
                "type": body_type,
            },
            "data": {
                "url": "s3://bucket/artifact.tar.gz"
            }
        }),
    }

def test_update_lambda_artifact_not_found(monkeypatch):
    """Verify that updating a non-existent artifact returns 404 status code."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")
    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = Exception("NoSuchKey")

    monkeypatch.setattr(
        update.boto3,
        "client",
        lambda service_name, *args, **kwargs: mock_s3
    )

    event = make_event()

    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")
    assert result["statusCode"] == 404


# ---------------------------------------------------------
# Validation failures
# ---------------------------------------------------------


def test_update_lambda_mismatched_artifact_type(monkeypatch):
    """Verify that mismatched artifact types in path and body return 400 status."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    # No AWS calls should happen
    monkeypatch.setattr(update.boto3, "client", MagicMock())

    event = make_event(
        path_type="model",
        body_type="dataset"  # mismatch
    )

    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")
    assert result["statusCode"] == 400
    assert "missing field" in result["body"]


def test_update_lambda_mismatched_id(monkeypatch):
    """Verify that mismatched IDs in path and body return 400 status."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    monkeypatch.setattr(update.boto3, "client", MagicMock())

    event = make_event(
        path_id="123",
        body_id="999"  # mismatch
    )

    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")
    assert result["statusCode"] == 400
    assert "missing field" in result["body"]


def test_update_lambda_missing_name(monkeypatch):
    """Verify that missing artifact name in body returns 400 status."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    monkeypatch.setattr(update.boto3, "client", MagicMock())

    event = make_event(name=None)

    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")
    assert result["statusCode"] == 400
    assert "missing field" in result["body"]

def test_lambda_invoke_failure(monkeypatch):
    """Verify that Lambda invocation failures return 403 status code."""
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(b"{}")}

    monkeypatch.setattr(
        update.boto3,
        "client",
        lambda service, *a, **k: mock_s3
    )

    mock_lambda = MagicMock()
    mock_lambda.invoke.side_effect = Exception("boom")

    monkeypatch.setattr(update, "lambda_client", mock_lambda)

    result = update.lambda_handler(make_event(), None)

    assert result["statusCode"] == 403