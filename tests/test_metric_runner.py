import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import types

# ===================================================================
# PRE-INJECTION: provide fake modules before importing metric_runner
# ===================================================================

# Fake metrics.registry so metric_runner can import METRIC_REGISTRY
fake_metrics_pkg = types.ModuleType("metrics")
fake_registry_mod = types.ModuleType("metrics.registry")

FAKE_REGISTRY = [
    ("metricA", lambda url, c, d: (0.9, 10)),
    ("metricB", lambda url, c, d: (0.8, 20)),
]

fake_registry_mod.METRIC_REGISTRY = FAKE_REGISTRY
fake_metrics_pkg.registry = fake_registry_mod

sys.modules["metrics"] = fake_metrics_pkg
sys.modules["metrics.registry"] = fake_registry_mod

# Fake run_metrics.calculate_net_score
fake_run_metrics = types.ModuleType("run_metrics")
fake_run_metrics.calculate_net_score = lambda results: 0.85
sys.modules["run_metrics"] = fake_run_metrics

# Fake metrics.utils.fetch_hf_readme_text
fake_utils_mod = types.ModuleType("metrics.utils")
fake_utils_mod.fetch_hf_readme_text = lambda url: "README TEXT"
sys.modules["metrics.utils"] = fake_utils_mod

# ===================================================================
# Now safe to import the code under test
# ===================================================================
from backend.Rate.metric_runner import run_all_metrics


# ===================================================================
# Fixture: mock AWS clients (bedrock + Upload lambda)
# ===================================================================
@pytest.fixture(autouse=True)
def mock_aws_clients():
    """
    - Patch boto3.client used inside metric_runner for Bedrock.
    - Patch the module-level lambda_client used for Upload.invoke.
    """
    with patch("backend.Rate.metric_runner.boto3.client") as mock_boto_client, \
         patch("backend.Rate.metric_runner.lambda_client") as mock_lambda_client:

        # ----- Bedrock mock -----
        bedrock_mock = MagicMock()
        bedrock_mock.invoke_model.return_value = {
            "body": MagicMock(
                read=lambda: json.dumps({
                    "output": {
                        "message": {
                            "content": [
                                {"text": "https://github.com/repo, https://dataset.org"}
                            ]
                        }
                    }
                }).encode("utf-8")
            )
        }

        # metric_runner only calls boto3.client for Bedrock; return this mock
        mock_boto_client.return_value = bedrock_mock

        # ----- Upload Lambda mock -----
        # Simulate Upload returning a simple API-style response:
        # {"statusCode": 201, "body": "OK"}
        upload_result_dict = {
            "statusCode": 201,
            "body": "OK",
        }
        payload_mock = MagicMock()
        payload_mock.read.return_value = json.dumps(upload_result_dict).encode("utf-8")

        mock_lambda_client.invoke.return_value = {"Payload": payload_mock}

        yield mock_lambda_client, bedrock_mock


# ===================================================================
# TESTS
# ===================================================================

def test_missing_artifact_type():
    # artifact_type or source_url missing -> 400
    resp = run_all_metrics({"artifact_type": None, "source_url": None}, None)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "error" in body
    assert "Missing artifact_type or source_url" in body["error"]


def test_readme_fetch_failure():
    # fetch_hf_readme_text returns None -> 500
    with patch("backend.Rate.metric_runner.fetch_hf_readme_text", return_value=None):
        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )
        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert "Failed to fetch README" in body["error"]


def test_metric_failure_returns_424():
    # One metric fails (score < 0.5) -> 424 and Upload is NOT invoked
    failing_registry = [
        ("metricA", lambda u, c, d: (0.1, 10)),  # failing score
        ("metricB", lambda u, c, d: (0.9, 20)),
    ]

    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", failing_registry):
        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None,
        )
        assert resp["statusCode"] == 424
        body = json.loads(resp["body"])
        assert "Model failed to pass metric checks" in body["error"]


def test_successful_run_returns_upload_response():
    # All metrics pass -> metric_runner forwards Upload's response
    event = {
        "artifact_type": "model",
        "source_url": "https://huggingface.co/test",
        "name": "model1",
    }

    resp = run_all_metrics(event, None)

    # Our mocked Upload returns {"statusCode": 201, "body": "OK"}
    assert resp["statusCode"] == 201
    assert resp["body"] == "OK"


def test_non_model_artifact_skips_metrics_and_calls_upload():
    # Non-model artifact: metrics block skipped, but Upload still invoked
    event = {
        "artifact_type": "dataset",
        "source_url": "https://example.com/ds",
        "name": "ds1",
    }

    resp = run_all_metrics(event, None)

    # Should still forward Upload's response
    assert resp["statusCode"] == 201
    assert resp["body"] == "OK"


##New stuff to hit coverage:


def test_bedrock_invocation_exception(monkeypatch):
    # Make bedrock.invoke_model raise
    def bad_invoke(*a, **kw):
        raise RuntimeError("bedrock fail")

    monkeypatch.setattr(
        "backend.Rate.metric_runner.boto3.client",
        lambda *a, **kw: MagicMock(invoke_model=bad_invoke)
    )

    resp = run_all_metrics(
        {"artifact_type": "model", "source_url": "x", "name": "m"},
        None
    )
    # It still proceeds to metric evaluation; all metrics succeed in FAKE_REGISTRY
    assert resp["statusCode"] == 201


def test_metric_execution_exception():
    bad_registry = [
        ("metricA", lambda u, c, d: (_ for _ in ()).throw(RuntimeError("fail"))),
        ("metricB", lambda u, c, d: (0.9, 20)),
    ]

    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", bad_registry):
        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None
        )

        # metricA fails → result should be 424 due to (None, 0)
        assert resp["statusCode"] == 424



def test_upload_returns_function_error():
    error_payload = MagicMock()
    error_payload.read.return_value = b'{"bad": "error"}'

    with patch("backend.Rate.metric_runner.lambda_client") as mock_lambda:
        mock_lambda.invoke.return_value = {
            "FunctionError": "Unhandled",
            "Payload": error_payload
        }

        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "test", "name": "m"},
            None
        )

        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert "Ingestor service" in body["error"]



def test_upload_invocation_raises_exception():
    with patch("backend.Rate.metric_runner.lambda_client") as mock_lambda:
        mock_lambda.invoke.side_effect = RuntimeError("upload fail")

        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None
        )

        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert "Internal error during final step handoff" in body["error"]


def test_event_parsing_exception():
    class BadEvent(dict):   # JSON serializable because it's a dict
        def get(self, *a, **kw):
            raise RuntimeError("boom")

    resp = run_all_metrics(BadEvent(), None)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "Internal processing error" in body["error"]



def test_bedrock_no_text_block(monkeypatch):
    # Bedrock returns content list WITHOUT any {"text": ...}
    bedrock_mock = MagicMock()
    bedrock_mock.invoke_model.return_value = {
        "body": MagicMock(
            read=lambda: json.dumps({
                "output": {"message": {"content": [{"not_text": "x"}]}}
            }).encode("utf-8")
        )
    }

    # Patch boto3 client to return our mock
    monkeypatch.setattr(
        "backend.Rate.metric_runner.boto3.client",
        lambda *a, **kw: bedrock_mock
    )

    # Patch METRIC_REGISTRY so metrics pass if reached
    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", [("m1", lambda *a: (1.0, 1))]):
        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None
        )

    # Still ends successfully and calls Upload
    assert resp["statusCode"] == 201


def test_metric_returns_non_tuple():
    bad_format_registry = [
        ("metricA", lambda *a: 0.75),  # Not a tuple → forces default branch
        ("metricB", lambda *a: (0.9, 10)),
    ]

    with patch("backend.Rate.metric_runner.METRIC_REGISTRY", bad_format_registry):
        resp = run_all_metrics(
            {"artifact_type": "model", "source_url": "x", "name": "m"},
            None
        )

    # Should succeed because scores are >= 0.5
    assert resp["statusCode"] == 201
