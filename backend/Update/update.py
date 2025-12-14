"""backend.Update.update

Lambda that receives artifact information and forwards them to the
`Rate` service. This module demonstrates synchronous invocation of the Rate
function and returning Rate's response to the API caller.

Exports:
- `lambda_handler(event, context)`: Validate input, prepare payload, invoke
  the downstream Rate Lambda, and return its response.
"""

import json
import boto3
import os

lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    """API Gateway entry point for artifact updates.
        Handles PUT /artifacts/{artifact_type}/{id}

    This function parses the path parameters and JSON body, validates required
    fields, forwards a payload to the `Rate` function, and relays the result.
    """

    # Log the incoming event for debugging.
    print("Received event:", json.dumps(event))

    # Extract artifact_type from path parameters (API Gateway proxy integration)
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type") or {}
    artifact_id = path_params.get("id") or {}

    # Parse body and extract URL
    try:
        body = json.loads(event.get("body", "{}"))
        name = body.get("metadata").get("name")
        id = body.get("metadata").get("id")
        type = body.get("metadata").get("type")
        url = body.get("data").get("url")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    # Validate required inputs
    if not artifact_type == type or not artifact_id == id or not name:
        return {"statusCode": 400, "body": json.dumps({"error": "There is missing field(s) in the artifact_type or artifact_id or it is formed improperly, or is invalid."})}

    # Check if artifact exists
    s3 = boto3.client("s3")
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        return {"statusCode": 500, "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})}

    s3_key = f"artifacts/{type}/{id}/metadata.json"

    try:
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    except Exception as e:
        return {"statusCode": 404, "body": json.dumps({"error": f"Artifact not found: {e}"})}


    # Prepare the payload that the Rate Lambda expects
    payload_for_Rate = {"artifact_type": artifact_type, "source_url": url, "name": name, "status": "received"}

    try:
        # Invoke Rate synchronously and forward its result to the API caller.
        response = lambda_client.invoke(FunctionName="Rate", InvocationType='RequestResponse', Payload=json.dumps(payload_for_Rate))

        # Read the payload returned by the Rate function and decode JSON
        response_payload_str = response['Payload'].read().decode('utf-8')
        rate_result = json.loads(response_payload_str)

        # Extract the status and adjust for Update response
        final_status_code = rate_result.get("statusCode", 403)
        if final_status_code == 201:
            final_status_code == 200

        # Relay the Rate status code back to the API Gateway caller
        return {"statusCode": final_status_code}

    except Exception as e:
        print(f"CRITICAL ERROR during synchronous invocation: {e}")
        return {"statusCode": 403, "body": json.dumps({"error": "Internal error during synchronous processing."})}
