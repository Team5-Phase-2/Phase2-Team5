"""backend.Rate.metrics.code_quality

Estimate code quality by linting Python example files with pylint and
mapping pylint scores into a small normalized scale.
"""

from typing import Optional, Tuple
import time, tempfile, subprocess, sys, os, requests
from urllib.parse import urlparse
from .utils import analyze_code


def code_quality(model_url: str, code_url: str, dataset_url: str) -> Tuple[Optional[float], int]:
    """Return (score, latency_ms) assessing repository code quality.

    The function attempts to fetch Python example files from the model
    repository and run `pylint` on them (requires `pylint` available in the
    execution environment). Pylint numeric scores are mapped to discrete
    buckets that are easier to combine with other metrics.
    """

    start_ns = time.time_ns()
    try:
        parsed_url = urlparse(code_url)
        if 'github.com' not in parsed_url.netloc:
            latency_ms = (time.time_ns() - start_ns) // 1_000_000
            return 0.5, latency_ms
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        # A standard GitHub repository URL is /owner/repo
        
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1]
            # Clean up the repo name if it ends with .git
            if repo.endswith('.git'):
                repo = repo[:-4]

        if not owner or not repo:
            latency_ms = (time.time_ns() - start_ns) // 1_000_000
            return 0.5, latency_ms


        
        contents_api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        response = requests.get(contents_api_url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to fetch repo contents. Status: {response.status_code}")
            return 0.5, (time.time_ns() - start_ns) // 1_000_000

        files_and_dirs = response.json()

        python_files = []
        for item in files_and_dirs:
            if isinstance(item, dict) and item.get("type") == "file" and item.get("name", "").endswith(".py"):
                # item["path"] is the full path within the repo
                python_files.append(item["path"])

        scores = []
        count = 0
        if python_files:
            for python_file in python_files:
                if count > 6:
                    break
                raw_file_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{python_file}"
                file_response = requests.get(raw_file_url, timeout=10)
                if file_response.status_code == 200:
                    sc = _analyze_with_pylint(file_response.text, python_file)
                    print(f"Pylint score for {python_file}: {sc}")
                    if sc is not None:
                        scores.append(sc)
                    count += 1
        else:
            print(f"Failed to fetch repo contents. Status: {response.status_code}")
            return 0.5, (time.time_ns() - start_ns) // 1_000_000

        score = sum(scores) / len(scores) if scores else 0
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return 0.5, latency_ms


def _analyze_with_pylint(code_content: str, filename: str) -> Optional[float]:
    """Run pylint on the provided code content and parse the resulting score.

    Writes code to a temporary file, invokes `python -m pylint` and parses
    the textual output. Returns mapped score buckets or None when analysis
    cannot be completed.
    """

    try:
        return analyze_code(code_content)
    except Exception as e:
        print(f"[ERROR] Lightweight analyzer failed for {filename}: {e}")
        return 0.5