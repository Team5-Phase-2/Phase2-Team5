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
