import json
import boto3

lambda_client = boto3.client('lambda')

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
    payload_for_Rate = {
        "artifact_type": artifact_type,
        "source_url": url,
        "status": "received",
    }

    try:
        # 4. Asynchronously invoke the 'Rate' Lambda
        # InvocationType='Event' makes it non-blocking (Fire-and-Forget)
        response = lambda_client.invoke(
            FunctionName= "Rate",
            InvocationType='RequestResponse',  # <<< KEY CHANGE: Async Call
            Payload=json.dumps(payload_for_Rate)
        )

        response_payload_str = response['Payload'].read().decode('utf-8')
        rate_result = json.loads(response_payload_str)

        final_status_code = rate_result.get("statusCode", 201)
        if(final_status_code == 201):
            final_body_content = rate_result.get("body", {})
        else: 
             final_body_content = {}
            
        if isinstance(final_body_content, dict):
             final_body_string = json.dumps(final_body_content)
        else:
             # Assumes 'Rate' already returned the body as a JSON string
             final_body_string = final_body_content


        # 4. Return the final result to the API Gateway user/client
        return {
            "statusCode": final_status_code,
            "body": final_body_string
        }

    except Exception as e:
            print(f"CRITICAL ERROR during synchronous invocation: {e}")
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Internal error during synchronous processing."})
            }
