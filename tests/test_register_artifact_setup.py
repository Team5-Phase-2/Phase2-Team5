import json
import pytest
from unittest.mock import patch, MagicMock

import backend.Register_Artifact_Setup.register_artifact_setup as ras


@pytest.fixture
def mock_lambda_client():
    """Patch ras.lambda_client so all invokes are intercepted."""
    with patch.object(ras, "lambda_client") as client:
        yield client


def test_invalid_json_body(mock_lambda_client):
    event = {
        "body": "{bad json",
        "pathParameters": {"artifact_type": "image"},
    }
    resp = ras.lambda_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Invalid JSON" in resp["body"]


def test_missing_required_fields(mock_lambda_client):
    # Missing artifact_type and url
    event = {
        "body": json.dumps({"name": "Test"}),
        "pathParameters": {},
    }
    resp = ras.lambda_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Missing artifact_type or url" in resp["body"]


def test_successful_rate_invocation(mock_lambda_client):
    # Mock Rate Lambda returned JSON payload
    fake_payload = MagicMock()
    fake_payload.read.return_value = json.dumps({
        "statusCode": 201,
        "body": {"result": "ok", "id": 123}
    }).encode()

    mock_lambda_client.invoke.return_value = {"Payload": fake_payload}

    event = {
        "pathParameters": {"artifact_type": "image"},
        "body": json.dumps({"url": "x.com", "name": "Sample"}),
    }

    resp = ras.lambda_handler(event, None)

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body == {"result": "ok", "id": 123}

    mock_lambda_client.invoke.assert_called_once()


def test_rate_returns_non_dict_body(mock_lambda_client):
    # Rate returns a body that is already a string → must be forwarded unchanged
    fake_payload = MagicMock()
    fake_payload.read.return_value = json.dumps({
        "statusCode": 202,
        "body": "STRING_BODY"
    }).encode()

    mock_lambda_client.invoke.return_value = {"Payload": fake_payload}

    event = {
        "pathParameters": {"artifact_type": "model"},
        "body": json.dumps({"url": "abc", "name": "model1"}),
    }

    resp = ras.lambda_handler(event, None)

    assert resp["statusCode"] == 202
    assert resp["body"] == "STRING_BODY"


def test_internal_exception_during_invoke(mock_lambda_client):
    mock_lambda_client.invoke.side_effect = Exception("boom")

    event = {
        "pathParameters": {"artifact_type": "image"},
        "body": json.dumps({"url": "x.com", "name": "Sample"}),
    }

    resp = ras.lambda_handler(event, None)

    assert resp["statusCode"] == 403
    assert "Internal error" in resp["body"]
