import boto3
import json
import os


def lambda_handler(event, context):
  """
    Parameters:
      artifact_type* : [model, dataset, code]
      id* : string
      dependency: bool (false)


    Return:
      statusCode:
        200: Return cost (MB)
        400: Bad request format
        404: Artifact doesn't exist
        500: server error
      body:
        id : {
          "total cost" : float (size MB)
        }
  """

  # Sanitize Request
  sanitized, error_response = sanitize_request(event)
  if error_response:
    return error_response

  id = sanitized["id"]
  artifact_type = sanitized["artifact_type"]
  dependency = sanitized["dependency"]

  s3 = boto3.client("s3")
  s3_bucket = os.environ.get("REGISTRY_BUCKET")


  artifact_name = None
  # Read name_id.txt from S3 bucket root to get artifact name mapping
  try:
    response = s3.get_object(Bucket=s3_bucket, Key="name_id.txt")
    name_id_content = response["Body"].read().decode("utf-8")
    
    # Parse name_id.txt to find matching artifact
    for line in name_id_content.strip().split("\n"):
      parts = line.split(",")
      if len(parts) == 3 and parts[1].strip() == id and parts[2].strip() == artifact_type:
        artifact_name = parts[0].strip()
        break
    
    if not artifact_name:
      return {
        "statusCode": 404,
        "body": json.dumps({"error": f"Artifact mapping not found for ID {id}"})
      }
  except s3.exceptions.NoSuchKey:
    return {
      "statusCode": 404,
      "body": json.dumps({"error": "Artifact registry file not found"})
    }


  # TODO: implement actual size calculation (S3 head_object, sum dependencies)
  try:
    s3_object = s3.head_object(Bucket=s3_bucket, Key=f"{artifact_name}.zip")
    total_cost_mb = s3_object["ContentLength"] / (1024 * 1024)
  except s3.exceptions.NoSuchKey:
    return {
      "statusCode": 404,
      "body": json.dumps({"error": "Artifact registry file not found"})
    }

  # For now return a placeholder success response indicating sanitized input
  return {
    "statusCode": 200,
    "body": json.dumps({
      "id": {
        "cost_mb": total_cost_mb
      }
    }),
  }


def sanitize_request(event):
  """Extract and validate expected parameters from an API Gateway event.

  Expected parameters:
    - pathParameters.artifact_type (model|dataset|code)
    - pathParameters.id (string)
    - queryStringParameters.dependency (optional, true/false) OR
      body.dependency when JSON body present

  Returns (sanitized_dict, error_response). On success error_response is None.
  """
  try:
    params = event.get("pathParameters", {}) or {}

    artifact_type = params.get("artifact_type", "")
    id = params.get("id", "")
    dependency_str = params.get("dependency", "false")
    dependency = str(dependency_str).lower() == "true"


    # Basic validation
    if not artifact_type or not isinstance(artifact_type, str):
      return {}, {"statusCode": 400, "body": json.dumps({"error": "Missing or invalid 'artifact_type' path parameter"})}

    allowed = {"model", "dataset", "code"}
    if artifact_type not in allowed:
      return {}, {"statusCode": 400, "body": json.dumps({"error": "Invalid artifact_type; must be one of model,dataset,code"})}

    if not id or not isinstance(id, str) or not id.strip():
      return {}, {"statusCode": 400, "body": json.dumps({"error": "Missing or invalid 'id' path parameter"})}

    return {"artifact_type": artifact_type, "id": id, "dependency": dependency}, None

  except Exception as e:
    return {}, {"statusCode": 400, "body": json.dumps({"error": "Invalid request", "detail": str(e)})}
