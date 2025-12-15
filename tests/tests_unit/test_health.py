"""Unit tests for the Health Lambda function.

Tests health check endpoints, logging, and CloudWatch integration.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import backend.Health.health as health_module


# ---------------------------------------------------------
# Mock environment patch (logs + cloudwatch + LOG_GROUPS=1)
# ---------------------------------------------------------
@pytest.fixture(autouse=True)
def aws_region(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


with patch("backend.Health.health.boto3.client") as boto_client:
    boto_client.return_value = MagicMock()
    import backend.Health.health as health_module

@pytest.fixture
def mock_env_small():
    with patch.object(health_module, "logs") as logs_mock, \
         patch.object(health_module, "cloudwatch") as cw_mock, \
         patch("backend.Health.health.LOG_GROUPS", ["x"]), \
         patch("backend.Health.health.time.sleep", return_value=None):

        yield logs_mock, cw_mock


# ---------------------------------------------------------
# Cover line 52: run_query fallback path
# ---------------------------------------------------------
def test_run_query_missing_status(mock_env_small):
    logs_mock, _ = mock_env_small

    logs_mock.start_query.return_value = {"queryId": "q123"}
    logs_mock.get_query_results.return_value = {"status": "Complete", "results": []}

    out = health_module.run_query("x", "q", 0, 1)
    assert out["results"] == []


# ---------------------------------------------------------
# Cover line 60: extract_count missing field fallback
# ---------------------------------------------------------
def test_extract_count_missing_field(mock_env_small):
    res = {"results": [[{"field": "zzz", "value": "10"}]]}
    assert health_module.extract_count(res, "missing") == 0


# ---------------------------------------------------------
# FIXED: Average latency empty
# ---------------------------------------------------------
def test_average_latency_empty(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    # get_metric_statistics → empty list → avg_latency_ms = 0
    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": []},             # avg latency
        {"Datapoints": [{"Sum": 5}]},   # request count MUST include "Sum"
    ]

    # get_metric_data required for p95/p99
    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [1],
            "Timestamps": [1],
        }]
    }

    logs_mock.start_query.return_value = {"queryId": "q"}
    logs_mock.get_query_results.return_value = {"status": "Complete", "results": []}

    stats = health_module.get_api_gateway_metrics(0, 1)
    assert stats["avg_latency_ms"] == 0


# ---------------------------------------------------------
# FIXED: Extended percentile empty → hits fallback and avoids KeyError
# ---------------------------------------------------------
def test_extended_percentile_empty(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": [{"Average": 1, "Timestamp": 1}]},  # avg
        {"Datapoints": [{"Sum": 7}]},                      # count
    ]

    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [],       # triggers fallback
            "Timestamps": [],   # avoids max()
        }]
    }

    logs_mock.start_query.return_value = {"queryId": "q"}
    logs_mock.get_query_results.return_value = {"status": "Complete", "results": []}

    stats = health_module.get_api_gateway_metrics(0, 1)
    assert stats["p95_latency_ms"] == 0
    assert stats["p99_latency_ms"] == 0


# ---------------------------------------------------------
# Cover line 228: return statement of lambda_handler
# ---------------------------------------------------------
def test_lambda_handler_return_line(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": [{"Average": 10, "Timestamp": 1}]},
        {"Datapoints": [{"Sum": 1}]},
    ]

    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [10],
            "Timestamps": [1],
        }]
    }

    logs_mock.start_query.return_value = {"queryId": "q"}
    logs_mock.get_query_results.return_value = {"status": "Complete", "results": []}

    resp = health_module.lambda_handler({}, None)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert "status" in body
    assert "api_gateway" in body
    assert "log_groups" in body


# ---------------------------------------------------------
# Cover line 52: run_query fallback when result["status"] is missing
# ---------------------------------------------------------
def test_run_query_missing_status_branch(mock_env_small):
    logs_mock, _ = mock_env_small

    logs_mock.start_query.return_value = {"queryId": "q999"}

    # FIRST result simulates AWS pending status → hits fallback branch (line 52)
    # SECOND result completes
    logs_mock.get_query_results.side_effect = [
        {"status": "Running", "results": []},  # triggers fallback loop, covers line 52
        {"status": "Complete", "results": []}  # exit condition
    ]

    out = health_module.run_query("x", "q", 0, 1)
    assert out["results"] == []



# ---------------------------------------------------------
# Cover line 175: if error_logs > 0 → health["status"] = "DEGRADED"
# ---------------------------------------------------------
def test_health_status_degraded_error_branch(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    # API metrics so status not degraded from zero requests
    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": [{"Average": 123, "Timestamp": 1}]},
        {"Datapoints": [{"Sum": 5}]},
    ]
    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [10],
            "Timestamps": [1],
        }]
    }

    logs_mock.start_query.return_value = {"queryId": "q"}

    # Force degradation (error_logs > 0)
    logs_mock.get_query_results.side_effect = [
        {"status": "Complete", "results": [[{"field": "total", "value": "10"}]]},
        {"status": "Complete", "results": [[{"field": "errors", "value": "2"}]]},  # hits line 175
        {"status": "Complete", "results": [[{"field": "warnings", "value": "0"}]]},
        {"status": "Complete", "results": []},
    ]

    # Call lambda_handler — required to get coverage for line 175
    resp = health_module.lambda_handler({}, None)
    body = json.loads(resp["body"])

    assert body["status"] == "DEGRADED"

def test_cover_line_175_requests_zero(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    # Make average latency irrelevant
    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": []},             # avg latency
        {"Datapoints": [{"Sum": 0}]},   # <-- ZERO REQUESTS → triggers line 175
    ]

    # Percentiles return empty (valid)
    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [],
            "Timestamps": [],
        }]
    }

    # Provide log group responses so iteration completes
    logs_mock.start_query.return_value = {"queryId": "Q"}
    logs_mock.get_query_results.return_value = {
        "status": "Complete",
        "results": [[{"field": "total", "value": "0"}]]
    }

    health = health_module.get_health_status()

    # Should be degraded due to ZERO requests
    assert health["status"] == "DEGRADED"




# ---------------------------------------------------------
# Cover line 228 fully by exercising lambda_handler under degraded status
# ---------------------------------------------------------
def test_lambda_handler_degraded_return_line(mock_env_small):
    logs_mock, cw_mock = mock_env_small

    cw_mock.get_metric_statistics.side_effect = [
        {"Datapoints": [{"Average": 50, "Timestamp": 1}]},
        {"Datapoints": [{"Sum": 1}]},
    ]

    cw_mock.get_metric_data.return_value = {
        "MetricDataResults": [{
            "Values": [42],
            "Timestamps": [1],
        }]
    }

    logs_mock.start_query.return_value = {"queryId": "q"}

    # Force degradation by having error logs > 0
    logs_mock.get_query_results.side_effect = [
        {"status": "Complete", "results": [[{"field": "total", "value": "5"}]]},
        {"status": "Complete", "results": [[{"field": "errors", "value": "3"}]]},
        {"status": "Complete", "results": [[{"field": "warnings", "value": "1"}]]},
        {"status": "Complete", "results": []},
    ]

    resp = health_module.lambda_handler({}, None)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["status"] == "DEGRADED"
