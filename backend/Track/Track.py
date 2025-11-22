import json

def lambda_handler(event, context):
  print("Received event:", json.dumps(event))

  return {
    "statusCode": 200,
    "body": json.dumps({"plannedTracks": "High-assurance track"})
  }
