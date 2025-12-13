"""backend.Regex.regex

Utilities for regex pattern safety validation.

Provides functions to check if a regex pattern is safe from potential
ReDoS (Regular expression Denial of Service) attacks by detecting
nested quantifiers, large repeats, and ambiguous alternations.
"""

import json
import re
import boto3

s3 = boto3.client("s3")

BUCKET_NAME = "cs461-team5-model-bucket"
FILE_KEY = "name_id.txt"   # update these

MAX_REPEAT_ALLOWED = 500   # adjust based on your needs


def is_unsafe_regex(pattern: str) -> str | None:
    """
    Simple regex safety checker.
    Blocks:
      - nested quantifiers       like (a+)+, (.+)+, (a*)*, (a+)*, etc.
      - extremely large repeats  like a{1,99999}
      - ambiguous alternation    like (a|aa)* or (foo|foobar)+
    Returns a string reason if unsafe, or None if safe.
    """

    # -------------------------------------------------------
    # 1. Nested quantifiers: (something+)+ , (.*)* , etc.
    # -------------------------------------------------------
    nested_quantifier_patterns = [
        r"\([^\)]*\+\)\+",     # (a+)+
        r"\([^\)]*\*\)\*",     # (a*)*
        r"\([^\)]*\?\)\?",     # (a?)?
        r"\([^\)]*\+\)\*",     # (a+)* or (a+{})* etc
        r"\([^\)]*\*\)\+",     # (a*)+
        r"\([^\)]*\+\)\?",     # (a+)?
        r"\([^\)]*\*\)\?",     # (a*)?
        r"\(\.\+\)\+",         # (.+)+
        r"\(\.\*\)\+",         # (.*)+
        r"\(\.\+\)\*",         # (.+)*
    ]

    for npat in nested_quantifier_patterns:
        if re.search(npat, pattern):
            return "Nested quantifiers detected"

    # Generic fallback: any ')<quantifier><quantifier>' sequence
    if re.search(r"\)([\+\*\?])\s*([\+\*\?])", pattern):
        return "Nested quantifiers detected"


    # -------------------------------------------------------
    # 2. Very large repeat ranges: {1,99999}
    # -------------------------------------------------------
    for lo, hi in re.findall(r"\{(\d+),(\d+)\}", pattern):
        if int(hi) > MAX_REPEAT_ALLOWED:
            return "Repeat range too large"


    # -------------------------------------------------------
    # 3. Ambiguous alternation inside repetition: (a|aa)* 
    #    → dangerous because one branch is prefix of another
    # -------------------------------------------------------
    repeated_groups = re.findall(r"\(([^)]+)\)([\*\+])", pattern)
    # repeated_groups gives list of ("a|aa", "*") etc.

    for group, quant in repeated_groups:
        branches = group.split("|")
        # prefix detection
        for a in branches:
            for b in branches:
                if a != b and (a.startswith(b) or b.startswith(a)):
                    return "Ambiguous alternation inside repetition"


    # -------------------------------------------------------
    # SAFE
    # -------------------------------------------------------
    return None


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

    unsafe_reason = is_unsafe_regex(pattern)
    if unsafe_reason:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unsafe regex: {unsafe_reason}"}),
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
    id_to_name_map = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue

        parts = [p.strip() for p in line.split(",")]

        # Expecting: name,id,type
        if len(parts) != 3:
            continue

        name, id_str, artifact_type = parts
        id_to_name_map[id_str] = name
        # Match against the regex
        if compiled.search(name):
            matches.append({
                "name": name,
                "id": id_str,
                "type": artifact_type
            })

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix="artifacts/")

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                object_key = obj['Key']
                
                # Check if the object is a README.md file (optional filtering, but good practice)
                if object_key.endswith('/README.md'):
                    print(f"Processing {object_key}")
                    # 2. Extract artifact_type and id from the key
                    # Key structure: artifacts/{artifact_type}/{id}/README.md
                    try:
                        # Split by '/', filter empty strings, and extract the parts
                        parts = object_key.split('/')
                        artifact_type = parts[1]
                        artifact_id = parts[2]
                        name = id_to_name_map.get(artifact_id, "Unknown Name")
                        
                        # 3. Read the object content
                        s3_object = s3.get_object(Bucket=BUCKET_NAME, Key=object_key)
                        readme_content = s3_object['Body'].read().decode('utf-8')
                        
                        # 4. Apply regex search
                        found_matches = re.findall(pattern, readme_content, re.IGNORECASE)
                        
                        if found_matches:
                            # Add to matches list in the required format
                            matches.append({
                                "name": name,
                                "id": artifact_id,
                                "type": artifact_type
                            })
                            
                    except Exception as e:
                        print(f"Error processing {object_key}: {e}")
                        continue

    if len(matches) == 0:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "No matches found"})
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(matches)
    }
