import json
import re
import boto3

s3 = boto3.client("s3")

BUCKET_NAME = "cs461-team5-model-bucket"
FILE_KEY = "name_id.txt" 
def lambda_handler(event, context):

    # extract regex pattern
    try:
        body = json.loads(event.get("body", "{}"))
        pattern = body.get("regex")
        if not pattern:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'regex' field"})
            }
    except Exception:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON body"})
        }

    compiled = re.compile(pattern, re.IGNORECASE)

    # read text file from S3
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=FILE_KEY)
        text = obj["Body"].read().decode("utf-8")
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Could not read S3 file: {str(e)}"})
        }

    # parse file lines
    matches = []

    for line in text.splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue

        parts = [p.strip() for p in line.split(",")]

        # Expecting: name,id,type
        if len(parts) != 3:
            continue

        name, id_str, artifact_type = parts

        # Match against the regex
        if compiled.search(name):
            matches.append({
                "name": name,
                "id": id_str,
                "type": artifact_type
            })



    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(matches)
    }
