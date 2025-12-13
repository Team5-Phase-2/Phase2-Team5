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
    """Verify that the print call occurs and receives properly serialized JSON."""
    event = {"foo": "bar"}

    with patch("builtins.print") as mock_print:
        resp = track.lambda_handler(event, None)

        # The handler must still return successfully
        assert resp["statusCode"] == 200

        # Ensure print() was called with JSON-serialized event
        mock_print.assert_called_with("Received event:", json.dumps(event))
