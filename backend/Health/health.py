"""backend.Health.health

Simple health-check Lambda. Returns HTTP 200 to indicate the service is up.
"""

import json


def lambda_handler(event, context):
    """Basic health-check endpoint.

    Logs the incoming event and returns a 200 status code. Used by uptime
    monitoring and load balancer health probes.
    """

    print("Received event:", json.dumps(event))
    return {"statusCode": 200}
