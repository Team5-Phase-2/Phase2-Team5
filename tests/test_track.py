"""Unit tests for the Track Lambda function.

Tests selected Track.
"""

import json
from unittest.mock import patch
import backend.Track.Track as track


def test_basic_response():
    """Ensure the handler returns the fixed 200 response with expected JSON."""
    event = {"key": "value"}

    resp = track.lambda_handler(event, None)

    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body == {"planned_tracks": "High-assurance track"}


def test_event_logging():
    """
    Track lambda does not log or print the event.
    This test only verifies successful execution.
    """
    event = {"foo": "bar"}

    resp = track.lambda_handler(event, None)

    assert resp["statusCode"] == 200

