"""Unit tests for the Delete Lambda function.

Tests artifact deletion, error handling, and AWS service interactions.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

import backend.Delete.delete as delete_module


# --------------------------------------------------
# FIXTURES
# --------------------------------------------------

@pytest.fixture
def set_env():
    """Set REGISTRY_BUCKET for tests."""
    os.environ["REGISTRY_BUCKET"] = "test-bucket"
    yield
    os.environ.pop("REGISTRY_BUCKET")


@pytest.fixture
def mock_s3():
    """Mock S3 client, paginator, and delete operations."""
    with patch("backend.Delete.delete.client") as mock_client:
        s3 = MagicMock()
        mock_client.return_value = s3  # client("s3") returns mocked client

        # Mock paginator
        paginator = MagicMock()
        s3.get_paginator.return_value = paginator

        yield s3, paginator


# --------------------------------------------------
# TEST CASES
# --------------------------------------------------

def test_missing_path_parameters():
    """Should return 400 when id or artifact_type is missing."""
    event = {"pathParameters": {}}

    resp = delete_module.delete_artifact(event, None)
    assert resp["statusCode"] == 400
    assert "Missing path parameter" in resp["body"]


def test_missing_environment_variable(mock_s3):
    """Should return 500 when REGISTRY_BUCKET is not set."""
    if "REGISTRY_BUCKET" in os.environ:
        os.environ.pop("REGISTRY_BUCKET")

    event = {"pathParameters": {"id": "123", "artifact_type": "model"}}

    resp = delete_module.delete_artifact(event, None)
    assert resp["statusCode"] == 500
    assert "REGISTRY_BUCKET" in resp["body"]


def test_artifact_not_found(set_env, mock_s3):
    """Paginator returns no 'Contents' → should return 404."""
    s3, paginator = mock_s3

    paginator.paginate.return_value = [
        {}  # No "Contents"
    ]

    event = {"pathParameters": {"id": "123", "artifact_type": "model"}}

    resp = delete_module.delete_artifact(event, None)

    assert resp["statusCode"] == 404
    assert "not found" in resp["body"]


def test_successful_delete(set_env, mock_s3):
    """Should delete all keys and return 200."""
    s3, paginator = mock_s3

    paginator.paginate.return_value = [
        {
            "Contents": [
                {"Key": "artifacts/model/123/file1.json"},
                {"Key": "artifacts/model/123/file2.json"},
            ]
        }
    ]

    event = {"pathParameters": {"id": "123", "artifact_type": "model"}}

    resp = delete_module.delete_artifact(event, None)

    assert resp["statusCode"] == 200

    # Ensure delete_objects was called with correct keys
    s3.delete_objects.assert_called_once()
    args, kwargs = s3.delete_objects.call_args
    assert kwargs["Delete"]["Objects"] == [
        {"Key": "artifacts/model/123/file1.json"},
        {"Key": "artifacts/model/123/file2.json"},
    ]


def test_s3_error_during_delete(set_env, mock_s3):
    """Simulate an S3 error and expect a 500 response."""
    s3, paginator = mock_s3

    paginator.paginate.side_effect = Exception("S3 Failure")

    event = {"pathParameters": {"id": "123", "artifact_type": "model"}}

    resp = delete_module.delete_artifact(event, None)

    assert resp["statusCode"] == 500
    assert "S3 Failure" in resp["body"]
