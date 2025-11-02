import json

def lambda_handler(event, context):
    """
    Handles POST /artifact/{artifact_type}
    Triggered by API Gateway
    On success, the return value triggers Lambda 'Rate'
    """
    print("Received event:", json.dumps(event))

    # 1. Extract path and body
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")

    try:
        body = json.loads(event.get("body", "{}"))
        url = body.get("url")
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    # 2. Validate input
    if not artifact_type or not url:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing artifact_type or url"})
        }

    # 3. Process the artifact
    # (replace with real logic)
    result = {
        "artifact_type": artifact_type,
        "source_url": url,
        "status": "received",
        "message": f"Artifact type '{artifact_type}' accepted."
    }

    # 4. Return JSON result
    # EventBridge will pass this into 'Rate' Lambda as responsePayload
    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }