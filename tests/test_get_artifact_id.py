import json
import os
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

import backend.Get_Artifact_Id.get_artifact_id as get_module


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def set_env():
    """Ensure REGISTRY_BUCKET is set."""
    os.environ["REGISTRY_BUCKET"] = "test-bucket"
    yield
    os.environ.pop("REGISTRY_BUCKET")


@pytest.fixture
def mock_s3():
    """
    Patch boto3.client so all S3 calls go to a MagicMock.
    Also inject a fake s3.exceptions.NoSuchKey so the handler’s
    'except s3.exceptions.NoSuchKey:' block does not raise TypeError.
    """
    with patch("backend.Get_Artifact_Id.get_artifact_id.boto3.client") as mock_client:

        s3 = MagicMock()
        mock_client.return_value = s3

        # ------------------------------------------------------------------
        # CRITICAL FIX: Without this, Python throws TypeError because the code
        # tries to catch 's3.exceptions.NoSuchKey', but MagicMock has no such
        # real exception class. So we create one.
        # ------------------------------------------------------------------
        class FakeNoSuchKey(Exception):
            pass

        s3.exceptions = MagicMock()
        s3.exceptions.NoSuchKey = FakeNoSuchKey
        # ------------------------------------------------------------------

        yield s3


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_missing_env_variable():
    """If REGISTRY_BUCKET is not set → 500."""
    if "REGISTRY_BUCKET" in os.environ:
        os.environ.pop("REGISTRY_BUCKET")

    event = {"pathParameters": {"artifact_type": "model", "id": "123"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 500
    assert "REGISTRY_BUCKET not configured" in resp["body"]


def test_missing_path_parameters(set_env):
    """Missing artifact_type or id → 400."""
    event = {"pathParameters": {}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Missing required parameters" in resp["body"]


def test_artifact_not_found_no_such_key(set_env, mock_s3):
    """
    NoSuchKey from S3 → should fall into generic ClientError or fallback path.
    Handler returns 400 because it cannot distinguish NoSuchKey correctly.
    """
    error = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
        "GetObject",
    )
    mock_s3.get_object.side_effect = error

    event = {"pathParameters": {"artifact_type": "model", "id": "999"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 404  # expected with current handler


def test_s3_error_other_than_no_such_key(set_env, mock_s3):
    """Any other ClientError → 400."""
    error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "No access"}},
        "GetObject",
    )
    mock_s3.get_object.side_effect = error

    event = {"pathParameters": {"artifact_type": "model", "id": "456"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 400


def test_unhandled_exception(set_env, mock_s3):
    """Generic Python exception → 400."""
    mock_s3.get_object.side_effect = Exception("Boom")

    event = {"pathParameters": {"artifact_type": "model", "id": "321"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 400


def test_malformed_metadata(set_env, mock_s3):
    """Metadata missing required fields → 400."""
    bad_metadata = json.dumps({"name": None}).encode()

    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: bad_metadata)
    }

    event = {"pathParameters": {"artifact_type": "model", "id": "111"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Malformed artifact record" in resp["body"]


def test_successful_retrieval(set_env, mock_s3):
    """Valid metadata → 200."""
    good_metadata = json.dumps({
        "name": "testmodel",
        "model_url": "http://example.com/model",
        "type": "model",
        "id": "123",
        "download_url": "http://example.com/download"
    }).encode()

    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: good_metadata)
    }

    event = {"pathParameters": {"artifact_type": "model", "id": "123"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])

    assert body["metadata"]["name"] == "testmodel"
    assert body["metadata"]["id"] == "123"
    assert body["metadata"]["type"] == "model"
    assert body["data"]["url"] == "http://example.com/model"
    assert body["data"]["download_url"] == "http://example.com/download"


def test_direct_nosuchkey_exception(set_env, mock_s3):
    """
    Forces the handler to hit the `except s3.exceptions.NoSuchKey` branch.
    This is the only branch still not covered.
    """

    class DirectNoSuchKey(mock_s3.exceptions.NoSuchKey):
        pass

    mock_s3.get_object.side_effect = DirectNoSuchKey("not found")

    event = {"pathParameters": {"artifact_type": "model", "id": "222"}}

    resp = get_module.get_artifact_handler(event, None)

    assert resp["statusCode"] == 404
