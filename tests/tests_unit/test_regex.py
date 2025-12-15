"""Unit tests for the Regex Lambda function.

Tests regex-based artifact searching, reDOS attacks, and S3 integration.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import backend.Regex.regex as regex_module


# ---------------------------------------------------------
# Fixture: mock S3 client + paginator
# ---------------------------------------------------------
@pytest.fixture
def mock_s3():
    with patch.object(regex_module, "s3") as s3_mock:
        yield s3_mock


# ---------------------------------------------------------
# 1. Invalid JSON → exercise error JSON path
# ---------------------------------------------------------
def test_missing_json_body(mock_s3):
    resp = regex_module.lambda_handler({"body": "{bad json"}, None)
    assert resp["statusCode"] == 400
    assert "Invalid JSON" in resp["body"]


# ---------------------------------------------------------
# 2. Missing "regex" field → covers missing-pattern branch (lines 44–45)
# ---------------------------------------------------------
def test_missing_regex_field(mock_s3):
    resp = regex_module.lambda_handler({"body": json.dumps({})}, None)
    assert resp["statusCode"] == 400
    assert "Missing 'regex'" in resp["body"]


# ---------------------------------------------------------
# 3. Unsafe regex patterns → cover explicit + generic checks
#    - (a+)+       → explicit nested-quantifier pattern
#    - a{1,999999} → large repeat range
#    - (.*)*       → explicit nested-quantifier pattern
#    - (a|aa)*     → ambiguous alternation
#    - (a)+?       → ONLY hits generic fallback ')<quant><quant>' (line 45)
# ---------------------------------------------------------
@pytest.mark.parametrize("pattern", [
    "(a+)+",        # explicit nested quantifier
    "a{1,999999}",  # huge repeat range
    "(.*)*",        # explicit nested quantifier
    "(a|aa)*",      # ambiguous alternation
    "(a)+?",        # triggers generic ')<quant><quant>' fallback
])
def test_unsafe_patterns(mock_s3, pattern):
    event = {"body": json.dumps({"regex": pattern})}
    resp = regex_module.lambda_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Unsafe regex" in resp["body"]


# ---------------------------------------------------------
# 4. S3 read failure → exercise 500 error path
# ---------------------------------------------------------
def test_s3_read_failure(mock_s3):
    mock_s3.get_object.side_effect = Exception("boom")

    event = {"body": json.dumps({"regex": "a"})}
    resp = regex_module.lambda_handler(event, None)

    assert resp["statusCode"] == 500
    assert "Could not read S3 file" in resp["body"]


# ---------------------------------------------------------
# 5. Successful match from name,id file
# ---------------------------------------------------------
def test_match_from_main_file(mock_s3):
    # Valid main file with two entries
    text_file_body = MagicMock()
    text_file_body.read.return_value = b"Alice,123,image\nBob,456,model"
    mock_s3.get_object.return_value = {"Body": text_file_body}

    fake_paginator = MagicMock()
    fake_paginator.paginate.return_value = [{"Contents": []}]
    mock_s3.get_paginator.return_value = fake_paginator

    event = {"body": json.dumps({"regex": "Ali"})}
    resp = regex_module.lambda_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0] == {"name": "Alice", "id": "123", "type": "image"}


# ---------------------------------------------------------
# 6. README.md match inside artifacts folder
#    (two matches total: main file + README)
# ---------------------------------------------------------
def test_match_in_readme(mock_s3):
    # Main name/id file
    text_file_body = MagicMock()
    text_file_body.read.return_value = b"Alice,123,image"
    mock_s3.get_object.return_value = {"Body": text_file_body}

    # README content with a match
    readme_body = MagicMock()
    readme_body.read.return_value = b"hello world ALICE is here"

    # Decide which file to return based on key
    def fake_get_object(Bucket, Key):
        if Key.endswith("README.md"):
            return {"Body": readme_body}
        return {"Body": text_file_body}

    mock_s3.get_object.side_effect = fake_get_object

    # Paginator returns a single README.md object
    fake_paginator = MagicMock()
    fake_paginator.paginate.return_value = [{
        "Contents": [{"Key": "artifacts/image/123/README.md"}]
    }]
    mock_s3.get_paginator.return_value = fake_paginator

    event = {"body": json.dumps({"regex": "alice"})}
    resp = regex_module.lambda_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    expected = {"name": "Alice", "id": "123", "type": "image"}
    # One match from main file, one from README
    assert len(body) == 2
    assert body.count(expected) == 2


# ---------------------------------------------------------
# 7. No matches → 404
# ---------------------------------------------------------
def test_no_matches(mock_s3):
    text_file_body = MagicMock()
    text_file_body.read.return_value = b"Alice,123,image\nBob,456,model"
    mock_s3.get_object.return_value = {"Body": text_file_body}

    fake_paginator = MagicMock()
    fake_paginator.paginate.return_value = [{"Contents": []}]
    mock_s3.get_paginator.return_value = fake_paginator

    event = {"body": json.dumps({"regex": "ZZZ"})}
    resp = regex_module.lambda_handler(event, None)

    assert resp["statusCode"] == 404
    assert "No matches" in resp["body"]


# ---------------------------------------------------------
# 8. Exercise README error path (except-block inside loop)
# ---------------------------------------------------------
def test_error_during_readme_processing(mock_s3):
    # Main file still valid
    text_body = MagicMock()
    text_body.read.return_value = b"Alice,123,image"
    mock_s3.get_object.return_value = {"Body": text_body}

    # Paginator returns one README.md object
    fake_paginator = MagicMock()
    fake_paginator.paginate.return_value = [{
        "Contents": [{"Key": "artifacts/image/123/README.md"}]
    }]
    mock_s3.get_paginator.return_value = fake_paginator

    # Error when trying to read README → triggers `except` + `continue`
    def fake_get_object(Bucket, Key):
        if Key.endswith("README.md"):
            raise ValueError("Test error inside README loop")
        return {"Body": text_body}

    mock_s3.get_object.side_effect = fake_get_object

    event = {"body": json.dumps({"regex": "alice"})}
    resp = regex_module.lambda_handler(event, None)

    # It should still succeed based on the main file match
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0] == {"name": "Alice", "id": "123", "type": "image"}


# ---------------------------------------------------------
# 9. NEW: Exercise skip branches for bad lines (lines 121 & 127)
#    - Line without comma        → `if not line or "," not in line: continue`
#    - Line with 2 parts only    → `if len(parts) != 3: continue`
# ---------------------------------------------------------
def test_skip_invalid_lines_in_main_file(mock_s3):
    text_file_body = MagicMock()
    text_file_body.read.return_value = b"""
NoCommaLine
OnlyTwo,Parts
Alice,123,image
"""
    mock_s3.get_object.return_value = {"Body": text_file_body}

    fake_paginator = MagicMock()
    fake_paginator.paginate.return_value = [{"Contents": []}]
    mock_s3.get_paginator.return_value = fake_paginator

    event = {"body": json.dumps({"regex": "Alice"})}
    resp = regex_module.lambda_handler(event, None)

    # Despite invalid lines, we still get the valid Alice match
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body) == 1
    assert body[0] == {"name": "Alice", "id": "123", "type": "image"}
