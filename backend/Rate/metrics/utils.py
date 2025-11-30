"""backend.Rate.metrics.utils

Small helpers used by metric implementations to fetch repository text and
resources. These helpers are intentionally simple and return empty strings on
transient errors to allow metrics to continue gracefully.
"""

import requests
import json
from os import environ
from scoring import _hf_model_id_from_url


def fetch_hf_readme_text(model_url: str) -> str:
    """Fetch raw README.md text from a Hugging Face model repository.

    The function converts the provided `model_url` to a canonical model id
    and attempts to fetch the README from the `main` branch. On any error an
    empty string is returned.
    """

    try:
        model_id = _hf_model_id_from_url(model_url)
        owner, repo = model_id.split("/", 1)
        raw_url = f"https://huggingface.co/{owner}/{repo}/raw/main/README.md"
        r = requests.get(raw_url, timeout=10)
        if r.status_code == 200:
            return r.text or ""
        return ""
    except Exception:
        # Network errors and malformed URLs result in an empty string.
        return ""


def query_genai(query: str) -> dict:
    try:
        api_key = environ.get("PURDUE_GENAI_API_KEY")
        api_key = 'sk-27f7d8c436b844b1ae6c3213e595670e'
    except Exception as e:
        return e, api_key

    url = "https://genai.rcac.purdue.edu/api/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "model": "llama3.3:70b",
        "messages": [
            {
                "role": "user",
                "content": query
            }
        ],
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()
        return {
            "statusCode": 200,
            "body": json.dumps(response.json())
        }
    except requests.exceptions.RequestException as e:
        return e, api_key
