"""backend.Health.health

Simple health-check Lambda. Returns HTTP 200 to indicate the service is up.
"""

import datetime
from datetime import timezone
import time
import json
import boto3

logs = boto3.client("logs")
cloudwatch = boto3.client("cloudwatch")

# ----- CONFIG -----
LOG_GROUPS = [
    "/aws/lambda/Register_Artifact_Setup",
    "/aws/lambda/Artifacts",
    "/aws/lambda/Get_Artifact_Id",
    "/aws/lambda/Get_Cost",
    "/aws/lambda/Get_Rate",
    "/aws/lambda/Rate",
    "/aws/lambda/Reset",
    "/aws/lambda/Upload",
    "api"   # add more if needed
]

API_GATEWAY_API_ID = "moy7eewxxe"
API_GATEWAY_STAGE = "main"

def run_query(log_group, query, start_ts, end_ts):
    """
    Execute a CloudWatch Logs Insights query for a given log group and time range,
    polling until the query completes or terminates.
    """
    response = logs.start_query(
        logGroupName=log_group,
        startTime=start_ts,
        endTime=end_ts,
        queryString=query,
        limit=500
    )
    query_id = response["queryId"]

    # Poll for results
    while True:
        result = logs.get_query_results(queryId=query_id)
        status = result["status"]

        if status in ["Complete", "Failed", "Cancelled"]:
            return result

        time.sleep(0.3)


def extract_count(result, field_name):
    """
    Extract an integer value for a given field from the first row
    of a CloudWatch Logs Insights query result.
    """
    if not result["results"]:
        return 0
    row = {f["field"]: f["value"] for f in result["results"][0]}
    return int(row.get(field_name, 0))


def get_api_gateway_metrics(start_dt, end_dt):
    """
    Retrieve API Gateway metrics for a specified time range.
    """

    def get_average_latency():
        """
        Fetch the average API Gateway latency for the configured API and stage
        over the given time range.
        """

        resp = cloudwatch.get_metric_statistics(
            Namespace="AWS/ApiGateway",
            MetricName="Latency",
            Dimensions=[
                {"Name": "ApiId", "Value": API_GATEWAY_API_ID},
                {"Name": "Stage", "Value": API_GATEWAY_STAGE}
            ],
            StartTime=start_dt,
            EndTime=end_dt,
            Period=300,
            Statistics=["Average"]
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return 0
        return sorted(datapoints, key=lambda x: x["Timestamp"])[-1]["Average"]

    def get_extended_percentile(percentile):
        """
        Retrieve the most recent API Gateway latency percentile value
        for the configured API and stage over the given time range.
        """
        query_id = f"p{percentile}latency"

        resp = cloudwatch.get_metric_data(
            MetricDataQueries=[
                {
                    "Id": query_id,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApiGateway",
                            "MetricName": "Latency",
                            "Dimensions": [
                                {"Name": "ApiId", "Value": API_GATEWAY_API_ID},
                                {"Name": "Stage", "Value": API_GATEWAY_STAGE},
                            ]
                        },
                        "Period": 300,
                        "Stat": f"p{percentile}"
                    },
                    "ReturnData": True
                }
            ],
            StartTime=start_dt,
            EndTime=end_dt,
            ScanBy="TimestampDescending"
        )

        results = resp["MetricDataResults"][0]
        values = results.get("Values", [])
        timestamps = results.get("Timestamps", [])

        if not values:
            return 0

        # Most recent value
        idx = timestamps.index(max(timestamps))
        return values[idx]

    def get_request_count():
        """
        Retrieve the total number of API Gateway requests over the given time range.
        """
        resp = cloudwatch.get_metric_statistics(
            Namespace="AWS/ApiGateway",
            MetricName="Count",
            Dimensions=[
                {"Name": "ApiId", "Value": API_GATEWAY_API_ID},
                {"Name": "Stage", "Value": API_GATEWAY_STAGE}
            ],
            StartTime=start_dt,
            EndTime=end_dt,
            Period=300,
            Statistics=["Sum"]
        )
        datapoints = resp.get("Datapoints", [])
        return int(sum(dp["Sum"] for dp in datapoints))

    return {
        "avg_latency_ms": get_average_latency(),
        "p95_latency_ms": get_extended_percentile(95),
        "p99_latency_ms": get_extended_percentile(99),
        "total_requests_last_hour": get_request_count()
    }



def get_health_status():
    """
    Collect API Gateway metrics and CloudWatch log statistics for the last hour
    and return a consolidated health status report.
    """
    now = datetime.datetime.now(timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)

    start_ts = int(one_hour_ago.timestamp())
    end_ts = int(now.timestamp())

    health = {
        "timestamp": now.isoformat(),
        "status": "OK",
        "api_gateway": {},
        "log_groups": []
    }

    # --------------------
    # API Gateway Metrics
    # --------------------
    api_stats = get_api_gateway_metrics(one_hour_ago, now)
    health["api_gateway"] = api_stats

    if api_stats["total_requests_last_hour"] == 0:
        health["status"] = "DEGRADED"

    # --------------------
    # Log Groups
    # --------------------
    for lg in LOG_GROUPS:

        # Queries (CloudWatch Logs Insights)
        total_query = "stats count(*) as total"
        error_count_query = """
            filter @message like /(?i)error/
            | stats count(*) as errors
        """
        warn_count_query = """
            filter @message like /(?i)warn/
            | stats count(*) as warnings
        """
        recent_error_query = """
            fields @timestamp, @message
            | filter @message like /(?i)error/
            | sort @timestamp desc
            | limit 20
        """

        # Run queries
        total_res = run_query(lg, total_query, start_ts, end_ts)
        error_res = run_query(lg, error_count_query, start_ts, end_ts)
        warn_res = run_query(lg, warn_count_query, start_ts, end_ts)
        recent_errors = run_query(lg, recent_error_query, start_ts, end_ts)

        # Extract numeric counts
        total_logs = extract_count(total_res, "total")
        error_logs = extract_count(error_res, "errors")
        warn_logs = extract_count(warn_res, "warnings")

        # Convert error log lines to list
        recent_errors_list = [
            {f["field"]: f["value"] for f in row}
            for row in recent_errors["results"]
        ]

        health["log_groups"].append({
            "name": lg,
            "summary": {
                "last_hour_total_logs": total_logs,
                "last_hour_errors": error_logs,
                "last_hour_warnings": warn_logs
            },
            "recent_errors": recent_errors_list
        })

        # If errors occurred in any log group, degrade status
        if error_logs > 0:
            health["status"] = "DEGRADED"

    return health

def lambda_handler(event, context):
    """
    AWS Lambda entry point that returns the current system health status
    as a JSON HTTP response.
    """
    health_data = get_health_status()

    return {
        "statusCode": 200,
        "body": json.dumps(health_data)
    }
