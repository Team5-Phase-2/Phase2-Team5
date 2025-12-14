import json
import io
import pytest
from unittest.mock import MagicMock

from backend.Update import update


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Happy path
# ---------------------------------------------------------

def test_update_lambda_success(monkeypatch):
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    # ---- Mock S3 ----
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {
        "Body": io.BytesIO(b"{}")
    }

    def mock_boto3_client(service_name, *args, **kwargs):
        if service_name == "s3":
            return mock_s3
        raise ValueError(f"Unexpected service: {service_name}")

    monkeypatch.setattr(update.boto3, "client", mock_boto3_client)

    # ---- Mock Lambda invoke ----
    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke.return_value = {
        "Payload": FakePayload({"statusCode": 201})
    }

    monkeypatch.setattr(update, "lambda_client", mock_lambda_client)

    # ---- Event ----
    event = make_event()

    # ---- Invoke ----
    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")

    # ---- Assert ----
    assert result["statusCode"] == 201  # reveals == vs = bug

    mock_s3.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="artifacts/model/123/metadata.json"
    )

    mock_lambda_client.invoke.assert_called_once()


# ---------------------------------------------------------
# Artifact does not exist
# ---------------------------------------------------------

def test_update_lambda_artifact_not_found(monkeypatch):
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
    monkeypatch.setenv("REGISTRY_BUCKET", "test-bucket")

    monkeypatch.setattr(update.boto3, "client", MagicMock())

    event = make_event(name=None)

    result = update.lambda_handler(event, None)

    print(f"[TEST] statusCode = {result['statusCode']}")
    assert result["statusCode"] == 400
    assert "missing field" in result["body"]


# ---------------------------------------------------------
# Lambda failure
# ---------------------------------------------------------

def test_lambda_invoke_failure(monkeypatch):
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