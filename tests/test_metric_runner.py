# tests/test_metric_runner.py

import json
import pytest
from unittest.mock import MagicMock, patch

import backend.Rate.metric_runner as mr


@pytest.fixture(autouse=True)
def mock_aws_clients():
    """
    Patch Bedrock + Upload lambda clients used by metric_runner.
    """
    with patch.object(mr.boto3, "client") as mock_boto, patch.object(mr, "lambda_client") as mock_lambda:
        # ---- Bedrock mock ----
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = {
            "body": MagicMock(
                read=lambda: json.dumps(
                    {
                        "output": {
                            "message": {
                                "content": [
                                    {"text": "https://github.com/repo, https://dataset.org"}
                                ]
                            }
                        }
                    }
                ).encode("utf-8")
            )
        }
        mock_boto.return_value = bedrock

        # ---- Upload mock (default success) ----
        payload = MagicMock()
        payload.read.return_value = json.dumps({"statusCode": 201, "body": "OK"}).encode("utf-8")
        mock_lambda.invoke.return_value = {"Payload": payload}

        yield


@pytest.fixture(autouse=True)
def fake_readme():
    # metric_runner requires README for model artifacts
    with patch.object(mr, "fetch_hf_readme_text", return_value="README TEXT"):
        yield


@pytest.fixture(autouse=True)
def fake_net_score():
    # if metric_runner calls calculate_net_score, keep it deterministic
    if hasattr(mr, "calculate_net_score"):
        with patch.object(mr, "calculate_net_score", return_value=0.85):
            yield
    else:
        yield


def test_missing_artifact_type():
    resp = mr.run_all_metrics({"artifact_type": None, "source_url": None}, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Missing artifact_type or source_url" in body["error"]


def test_readme_fetch_failure():
    with patch.object(mr, "fetch_hf_readme_text", return_value=None):
        resp = mr.run_all_metrics({"artifact_type": "model", "source_url": "x", "name": "m"}, None)
    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "Failed to fetch README" in body["error"]


def test_metric_failure_returns_424():
    failing_registry = [
        ("metricA", lambda u, c, d: (0.1, 10)),
        ("metricB", lambda u, c, d: (0.9, 20)),
    ]
    with patch.object(mr, "METRIC_REGISTRY", failing_registry):
        resp = mr.run_all_metrics({"artifact_type": "model", "source_url": "x", "name": "m"}, None)

    assert resp["statusCode"] == 424
    body = json.loads(resp["body"])
    assert "failed to pass metric checks" in body["error"].lower()


def test_successful_run():
    passing_registry = [
        ("metricA", lambda u, c, d: (0.9, 10)),
        ("metricB", lambda u, c, d: (0.8, 20)),
    ]
    with patch.object(mr, "METRIC_REGISTRY", passing_registry):
        resp = mr.run_all_metrics(
            {"artifact_type": "model", "source_url": "https://huggingface.co/test", "name": "model1"},
            None,
        )

    assert resp["statusCode"] == 201
    assert resp["body"] == "OK"


def test_non_model_artifact_skips_metrics():
    resp = mr.run_all_metrics({"artifact_type": "dataset", "source_url": "x", "name": "d"}, None)
    assert resp["statusCode"] == 201
    assert resp["body"] == "OK"


def test_metric_execution_exception_returns_424():
    bad_registry = [
        ("metricA", lambda u, c, d: (_ for _ in ()).throw(RuntimeError("fail"))),
        ("metricB", lambda u, c, d: (0.9, 20)),
    ]
    with patch.object(mr, "METRIC_REGISTRY", bad_registry):
        resp = mr.run_all_metrics({"artifact_type": "model", "source_url": "x", "name": "m"}, None)

    assert resp["statusCode"] == 424


def test_upload_returns_function_error():
    passing_registry = [("metricA", lambda u, c, d: (0.9, 10))]
    with patch.object(mr, "METRIC_REGISTRY", passing_registry), patch.object(mr, "lambda_client") as mock_lambda:
        payload = MagicMock()
        payload.read.return_value = b'{"bad":"error"}'
        mock_lambda.invoke.return_value = {"FunctionError": "Unhandled", "Payload": payload}

        resp = mr.run_all_metrics({"artifact_type": "model", "source_url": "x", "name": "m"}, None)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "ingestor service" in body["error"].lower()


def test_upload_invocation_raises_exception():
    passing_registry = [("metricA", lambda u, c, d: (0.9, 10))]
    with patch.object(mr, "METRIC_REGISTRY", passing_registry), patch.object(mr, "lambda_client") as mock_lambda:
        mock_lambda.invoke.side_effect = RuntimeError("boom")

        resp = mr.run_all_metrics({"artifact_type": "model", "source_url": "x", "name": "m"}, None)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "internal error" in body["error"].lower()
