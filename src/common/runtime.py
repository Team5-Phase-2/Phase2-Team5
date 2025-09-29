# src/common/runtime.py
from __future__ import annotations

import os
import sys
import json
from typing import Tuple, Dict, Any, Optional

# You can use either urllib (stdlib) or requests (optional).
# We'll provide both paths; the default uses urllib so you have no extra deps.
import urllib.request
import urllib.error

# Internal: gate printing the warning exactly once per process
_GH_BAD_TOKEN_REPORTED = False


def gh_headers(include_token: bool = True) -> Dict[str, str]:
    """
    Build GitHub API headers. If a token is present in the environment and
    include_token=True, add the Authorization header. Reads env every call.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ece461-team/1.0",
    }
    if include_token:
        token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def github_get(url: str, timeout: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
    """
    Fetch JSON from the GitHub API using urllib (stdlib), with robust handling:
      - If a token is set and GitHub returns 401/403, print EXACTLY
        'Invalid GitHub Token' to stderr ONCE, then retry unauthenticated.
      - Never print to stdout. Never raise. Returns (ok, data_dict_or_empty).

    Example:
        ok, data = github_get("https://api.github.com/rate_limit")
        if ok:
            # use data
    """
    global _GH_BAD_TOKEN_REPORTED

    # First attempt: include Authorization if present
    req = urllib.request.Request(url, headers=gh_headers(include_token=True))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            return True, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as e:
        # If token was sent and rejected, warn once and retry without token
        sent_token = "Authorization" in req.headers
        if e.code in (401, 403) and sent_token:
            if not _GH_BAD_TOKEN_REPORTED:
                # EXACT message (case & wording) — goes to stderr
                sys.stderr.write("Invalid GitHub Token\n")
                _GH_BAD_TOKEN_REPORTED = True
            # Retry without token
            req2 = urllib.request.Request(url, headers=gh_headers(include_token=False))
            try:
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                    payload2 = resp2.read().decode("utf-8")
                    return True, (json.loads(payload2) if payload2 else {})
            except Exception:
                return False, {}
        # Other HTTP errors → return False, don’t raise
        return False, {}
    except Exception:
        # Network/parse issues → return False
        return False, {}


# OPTIONAL: If you prefer requests() in some parts of your code, use this helper.
# It behaves the same (prints the warning once, then retries without token).
def github_get_requests(url: str, timeout: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
    """
    Same behavior as github_get(), but uses 'requests' if you prefer.
    Safe to import even if 'requests' is missing (we fall back to urllib).
    """
    try:
        import requests  # local import to avoid hard dependency
    except Exception:
        # Fallback to urllib-based helper if requests is unavailable
        return github_get(url, timeout=timeout)

    global _GH_BAD_TOKEN_REPORTED

    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    headers = gh_headers(include_token=bool(token))
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 401 or r.status_code == 403:
            if token:
                if not _GH_BAD_TOKEN_REPORTED:
                    sys.stderr.write("Invalid GitHub Token\n")
                    _GH_BAD_TOKEN_REPORTED = True
                # Retry without token
                r2 = requests.get(url, headers=gh_headers(include_token=False), timeout=timeout)
                if r2.ok:
                    try:
                        return True, r2.json()
                    except Exception:
                        return True, {}
                return False, {}
        if r.ok:
            try:
                return True, r.json()
            except Exception:
                return True, {}
        return False, {}
    except Exception:
        return False, {}
    

_validated_once = False
def validate_github_token_once() -> None:
    """Ping a cheap endpoint so a bad token triggers the required stderr message exactly once."""
    global _validated_once
    if _validated_once:
        return
    _validated_once = True
    # super cheap endpoint; doesn’t affect stdout
    github_get("https://api.github.com/rate_limit", timeout=5.0)
