import os, sys, logging, json, urllib.request, urllib.error

GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()

def github_headers():
    h = {"Accept": "application/vnd.github+json", "User-Agent": "ece461-team9/1.0"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h

def github_get(url: str, timeout: float = 10.0):
    """GET with graceful fallback if token is invalid/unauthorized."""
    req = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 401/403 → retry without Authorization
        if e.code in (401, 403) and GITHUB_TOKEN:
            logging.warning("GitHub token unauthorized; retrying unauthenticated")
            req2 = urllib.request.Request(
                url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ece461-team9/1.0"}
            )
            try:
                with urllib.request.urlopen(req2, timeout=timeout) as r2:
                    return True, json.loads(r2.read().decode("utf-8"))
            except Exception:
                return False, {}
        return False, {}
    except Exception:
        return False, {}
    
'''
def init_logging():
    import logging
    LOG_FILE  = (os.getenv("LOG_FILE") or "").strip()
    LOG_LEVEL = int(os.getenv("LOG_LEVEL") or "0")

    level = logging.ERROR
    if LOG_LEVEL == 1:
        level = logging.INFO
    elif LOG_LEVEL >= 2:
        level = logging.DEBUG

    handlers = []
    if LOG_FILE:
        try:
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            handlers.append(fh)
        except Exception:
            # invalid path -> fall back to stderr
            handlers.append(logging.StreamHandler(sys.stderr))
    else:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(levelname)s:%(message)s"
    )
'''