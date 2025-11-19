import json
import os
import uuid
import hashlib
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Handles POST /artifact/{artifact_type}
    Triggered by API Gateway.
    On success, writes metadata to S3 and returns 201 Created.
    """

    print("Received event:", json.dumps(event))

    #Enviroment Variable for the S3 Bucket: 
    s3_bucket = os.environ.get("REGISTRY_BUCKET")
    if not s3_bucket:
        #ERROR: no s3 bucket 
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "REGISTRY_BUCKET not configured"})
        }

    #create s3 client to upload files 
    s3 = boto3.client("s3")

    #Get artifact type
    '''
    path_params = event.get("pathParameters", {}) or {}
    artifact_type = path_params.get("artifact_type")
    '''

    #Confirm JSON body exists
    body = event

    #Expected filds in body
    artifact_type = body.get("artifact_type")
    model_url = body.get("model_url")
    results = body.get("results")
    net_score = body.get("net_score")
    #ingest = body.get("ingest")

    #If inputs not present throw 400 error
    if not artifact_type or not model_url or results is None or net_score is None: #or ingest is None:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Missing one or more required fields: "
                         "artifact_type, model_url, results, net_score, ingest"
            })
        }
    
    #confirm ingest is correct type
    '''
    if not isinstance(ingest, bool):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Field 'ingest' must be a boolean (true or false)"})
        }
    '''

    #create model id from the url 
    name = model_url.rstrip("/").split("/")[-1]

    #create almost perfect unique id to match spec (uses last 10 digits of int converted uuid)
    #model_id = int(str(uuid.uuid4().int)[-10:])
    hash_object = hashlib.sha256(name.encode())
    numeric_hash = int(hash_object.hexdigest(), 16) 
    model_id = numeric_hash % 9999999967

    #Create output to upload and return 
    output = {
        "type": artifact_type,
        "model_url": model_url,
        "results": results,
        "net_score": net_score,
        "name": name,
        "model_id": model_id 
    }

    metadata = {
        "name": name,
        "id": model_id,
        "type": artifact_type
    }

    data = {
        "url": model_url
    }

    #if ingest is false do not upload and return 
    '''
    if not ingest:
        
        response_body = {
            "message": "Ingest flag is false; model not stored.",
            "data": data
        }
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response_body)
        }
    '''

    #Write to s3 
    s3_key = f"artifacts/{artifact_type}/{model_id}/metadata.json"
    try:
        s3.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=json.dumps(output, indent=2),
            ContentType="application/json"
        )
    except ClientError as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to write to S3", "detail": str(e)})
        }

    #create object to return 
    response_body = {
        "metadata": metadata,
        "data": data
    }

    #return successful upload 
    return {
        "statusCode": 201,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response_body)
    }
