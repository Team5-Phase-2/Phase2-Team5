# tests/test_metric_runner.py

import json
import pytest
import sys
import types
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def isolated_metric_runner_env():
    """
    Provide fake modules ONLY during metric_runner tests.
    Never use monkeypatch here (scope mismatch).
    """
    original_modules = sys.modules.copy()

    injected = {
        "metrics",
        "metrics.registry",
        "metrics.utils",
        "run_metrics",
    }

    # ---- Fake metrics.registry ----
    fake_metrics_pkg = types.ModuleType("metrics")
    fake_registry_mod = types.ModuleType("metrics.registry")
    fake_registry_mod.METRIC_REGISTRY = [
        ("metricA", lambda u, c, d: (0.9, 10)),
        ("metricB", lambda u, c, d: (0.8, 20)),
    ]
    fake_metrics_pkg.registry = fake_registry_mod

    sys.modules["metrics"] = fake_metrics_pkg
    sys.modules["metrics.registry"] = fake_registry_mod

    # ---- Fake run_metrics ----
    fake_run_metrics = types.ModuleType("run_metrics")
    fake_run_metrics.calculate_net_score = lambda results: 0.85
    sys.modules["run_metrics"] = fake_run_metrics

    # ---- Fake metrics.utils ----
    fake_utils = types.ModuleType("metrics.utils")
    fake_utils.fetch_hf_readme_text = lambda _: "README TEXT"
    sys.modules["metrics.utils"] = fake_utils

    yield

    # ✅ SAFE cleanup (no sys.modules.clear!)
    for k in injected:
        sys.modules.pop(k, None)

    for k, v in original_modules.items():
        if k not in sys.modules:
            sys.modules[k] = v


@pytest.fixture
def metric_runner():
    from backend.Rate.metric_runner import run_all_metrics
    return run_all_metrics


@pytest.fixture(autouse=True)
def mock_aws_clients():
    with patch("backend.Rate.metric_runner.boto3.client") as mock_boto, \
         patch("backend.Rate.metric_runner.lambda_client") as mock_lambda:

        # ---- Bedrock mock ----
        bedrock = MagicMock()
        bedrock.invoke_model.return_value = {
            "body": MagicMock(
                read=lambda: json.dumps({
                    "output": {
                        "message": {
                            "content": [{"text": "https://github.com/repo"}]
                        }
                    }
                }).encode()
            )
        }
        mock_boto.return_value = bedrock

        # ---- Upload mock ----
        payload = MagicMock()
        payload.read.return_value = json.dumps({
            "statusCode": 201,
            "body": "OK"
        }).encode()

        mock_lambda.invoke.return_value = {"Payload": payload}

        yield


def test_missing_artifact_type(metric_runner):
    resp = metric_runner({"artifact_type": None, "source_url": None}, None)
    assert resp["statusCode"] == 400


def test_readme_fetch_failure(metric_runner):
    with patch("backend.Rate.metric_runner.fetch_hf_readme_text", return_value=None):
        resp = metric_runner(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )
    assert resp["statusCode"] == 500


def test_metric_failure_returns_424(metric_runner):
    failing_registry = [
        ("metricA", lambda *_: (0.1, 10)),
        ("metricB", lambda *_: (0.9, 10)),
    ]

    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", failing_registry):
        resp = metric_runner(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )

    assert resp["statusCode"] == 424


def test_successful_run(metric_runner):
    resp = metric_runner(
        {
            "artifact_type": "model",
            "source_url": "https://huggingface.co/test",
            "name": "m",
        },
        None,
    )
    assert resp["statusCode"] == 201
    assert resp["body"] == "OK"


def test_non_model_artifact_skips_metrics(metric_runner):
    resp = metric_runner(
        {"artifact_type": "dataset", "source_url": "x", "name": "d"},
        None,
    )
    assert resp["statusCode"] == 201


def test_metric_execution_exception(metric_runner):
    bad_registry = [
        ("metricA", lambda *_: (_ for _ in ()).throw(RuntimeError("fail"))),
        ("metricB", lambda *_: (0.9, 10)),
    ]

    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", bad_registry):
        resp = metric_runner(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )

    assert resp["statusCode"] == 424


def test_upload_returns_function_error(metric_runner):
    payload = MagicMock()
    payload.read.return_value = b'{"error":"bad"}'

    with patch("backend.Rate.metric_runner.lambda_client") as mock_lambda:
        mock_lambda.invoke.return_value = {
            "FunctionError": "Unhandled",
            "Payload": payload,
        }

        resp = metric_runner(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )

    assert resp["statusCode"] == 500


def test_upload_invocation_raises(metric_runner):
    with patch("backend.Rate.metric_runner.lambda_client") as mock_lambda:
        mock_lambda.invoke.side_effect = RuntimeError("boom")

        resp = metric_runner(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )

    assert resp["statusCode"] == 500
