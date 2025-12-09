import json
import os
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Correct import path for your project
import backend.Get_Cost.Get_Cost as get_cost_module


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def set_env():
    """Ensure REGISTRY_BUCKET is set."""
    os.environ["REGISTRY_BUCKET"] = "test-bucket"
    yield
    os.environ.pop("REGISTRY_BUCKET")


@pytest.fixture
def mock_s3():
    """Patch boto3.client so all S3 calls go through a MagicMock."""
    with patch("backend.Get_Cost.Get_Cost.boto3.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3
        yield s3


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

def test_missing_params():
    """Missing artifact_type or id → 400"""
    event = {"pathParameters": {}}
    resp = get_cost_module.lambda_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Missing artifact_type or id" in resp["body"]


def test_missing_env_variable(mock_s3):
    """REGISTRY_BUCKET missing should still cause a 404 on not-found errors."""
    if "REGISTRY_BUCKET" in os.environ:
        os.environ.pop("REGISTRY_BUCKET")

    err = ClientError(
        {"Error": {"Code": "404", "Message": "Not found"}},
        "HeadObject",
    )
    mock_s3.head_object.side_effect = err

    event = {"pathParameters": {"artifact_type": "model", "id": "abc"}}
    resp = get_cost_module.lambda_handler(event, None)

    assert resp["statusCode"] == 404


@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound"])
def test_artifact_not_found_codes(set_env, mock_s3, code):
    """File not found → 404"""
    err = ClientError(
        {"Error": {"Code": code, "Message": "Missing"}},
        "HeadObject",
    )
    mock_s3.head_object.side_effect = err

    event = {"pathParameters": {"artifact_type": "model", "id": "xyz"}}

    resp = get_cost_module.lambda_handler(event, None)

    assert resp["statusCode"] == 404
    assert "not found" in resp["body"].lower()


def test_unexpected_client_error(set_env, mock_s3):
    """Unexpected S3 ClientError should cause handler to crash (UnboundLocalError)."""
    err = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
        "HeadObject",
    )
    mock_s3.head_object.side_effect = err

    event = {"pathParameters": {"artifact_type": "model", "id": "abc"}}

    with pytest.raises(UnboundLocalError):
        get_cost_module.lambda_handler(event, None)



def test_generic_exception(set_env, mock_s3):
    """Generic exception should bubble up and crash the handler."""
    mock_s3.head_object.side_effect = Exception("Boom")

    event = {"pathParameters": {"artifact_type": "model", "id": "abc"}}

    with pytest.raises(Exception):
        get_cost_module.lambda_handler(event, None)



def test_success_response(set_env, mock_s3):
    """Successful head_object → return cost."""
    mock_s3.head_object.return_value = {"ContentLength": 5_242_880}  # 5 MB

    event = {"pathParameters": {"artifact_type": "model", "id": "m123"}}

    resp = get_cost_module.lambda_handler(event, None)

    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert "m123" in body
    assert body["m123"]["total_cost"] == 5  # rounded
