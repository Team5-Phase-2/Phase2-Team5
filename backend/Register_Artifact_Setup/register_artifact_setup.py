"""backend.Register_Artifact_Setup.register_artifact_setup

Lambda that receives artifact registration requests and forwards them to the
`Rate` service. This module demonstrates synchronous invocation of the Rate
function and returning Rate's response to the API caller.

Exports:
- `lambda_handler(event, context)`: Validate input, prepare payload, invoke
  the downstream Rate Lambda, and return its response.
"""

import json
import boto3

lambda_client = boto3.client('lambda')


def lambda_handler(event, context):
    """API Gateway entry point for artifact registration.
        Handles POST /artifact/{artifact_type}

    This function parses the path parameters and JSON body, validates required
    fields, forwards a payload to the `Rate` function, and relays the result.
    """

    # Log the incoming event for debugging.
    print("Received event:", json.dumps(event))

    # Extract artifact_type from path parameters (API Gateway proxy integration)
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")

    # Parse body and extract URL
    try:
        body = json.loads(event.get("body", "{}"))
        url = body.get("url")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON"})}

    # Validate required inputs
    if not artifact_type or not url:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing artifact_type or url"})}

    # Prepare the payload that the Rate Lambda expects
    payload_for_Rate = {"artifact_type": artifact_type, "source_url": url, "status": "received"}

    try:
        # Invoke Rate synchronously and forward its result to the API caller.
        response = lambda_client.invoke(FunctionName="Rate", InvocationType='RequestResponse', Payload=json.dumps(payload_for_Rate))

        # Read the payload returned by the Rate function and decode JSON
        response_payload_str = response['Payload'].read().decode('utf-8')
        rate_result = json.loads(response_payload_str)

        # Extract the status and body from Rate's return value (if present)
        final_status_code = rate_result.get("statusCode", 403)
        final_body_content = rate_result.get("body", {})

        # Normalize the body to a JSON string
        if isinstance(final_body_content, dict):
            final_body_string = json.dumps(final_body_content)
        else:
            final_body_string = final_body_content

        # Relay the Rate response back to the API Gateway caller
        return {"statusCode": final_status_code, "body": final_body_string}

    except Exception as e:
        print(f"CRITICAL ERROR during synchronous invocation: {e}")
        return {"statusCode": 403, "body": json.dumps({"error": "Internal error during synchronous processing."})}
