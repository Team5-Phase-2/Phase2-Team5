"""backend.Rate.metrics.code_quality

Estimate code quality by linting Python example files with pylint and
mapping pylint scores into a small normalized scale.
"""

from typing import Optional, Tuple
import time, tempfile, subprocess, sys, os, requests
from urllib.parse import urlparse


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
            return None, latency_ms
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
            return None, latency_ms


        
        contents_api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
        response = requests.get(contents_api_url, timeout=10)
        
        if response.status_code != 200:
            print(f"Failed to fetch repo contents. Status: {response.status_code}")
            return None, (time.time_ns() - start_ns) // 1_000_000

        files_and_dirs = response.json()

        python_files = []
        for item in files_and_dirs:
            if isinstance(item, dict) and item.get("type") == "file" and item.get("name", "").endswith(".py"):
                # item["path"] is the full path within the repo
                python_files.append(item["path"])

        scores = []
        if python_files:
            for python_file in python_files:
                raw_file_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{python_file}"
                file_response = requests.get(raw_file_url, timeout=10)
                if file_response.status_code == 200:
                    sc = _analyze_with_pylint(file_response.text, python_file)
                    print(f"Pylint score for {python_file}: {sc}")
                    if sc is not None:
                        scores.append(sc)
        else:
            print(f"Failed to fetch repo contents. Status: {response.status_code}")
            return None, (time.time_ns() - start_ns) // 1_000_000

        score = sum(scores) / len(scores) if scores else 0
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms


def _analyze_with_pylint(code_content: str, filename: str) -> Optional[float]:
    """Run pylint on the provided code content and parse the resulting score.

    Writes code to a temporary file, invokes `python -m pylint` and parses
    the textual output. Returns mapped score buckets or None when analysis
    cannot be completed.
    """

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(code_content)
            temp_file_path = temp_file.name

        result = subprocess.run(
            [sys.executable, "-m", "pylint", "--output-format=text", "--score=yes", temp_file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(result.stdout)
        return _parse_pylint_score(result.stdout)

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception:
            pass


def _parse_pylint_score(output: str) -> Optional[float]:
    """Parse pylint output and map numeric score to a small set of buckets."""

    for line in output.split('\n'):
        if 'Your code has been rated at' in line:
            try:
                parts = line.split('rated at')[-1].strip().split('/')
                raw_score = float(parts[0])
                if raw_score >= 7:
                    return 1
                elif raw_score >= 4:
                    return 0.75
                elif raw_score >= 2:
                    return 0.5
                elif raw_score >= 0.1:
                    return 0.25
            except (ValueError, IndexError):
                continue
    return None


if __name__ == "__main__":

    test_code_url = "https://github.com/mv-lab/swin2sr"
    
    # The function requires model_url and dataset_url, but they are not used 
    # in the current GitHub-focused logic, so we pass placeholders.
    model_url_placeholder = "http://placeholder.co/model"
    dataset_url_placeholder = "http://placeholder.co/dataset"
    
    print(f"\n--- Running Code Quality Analysis ---")
    print(f"Target Repository: {test_code_url}")
    
    # --- Function Call ---
    final_score, latency_ms = code_quality(
        model_url=model_url_placeholder, 
        code_url=test_code_url, 
        dataset_url=dataset_url_placeholder
    )
    
    # --- Results ---
    print("\n--- Analysis Results ---")
    if final_score is not None:
        print(f"✅ Code Quality Score (Normalized): {final_score:.2f}")
        print(f"⏱️ Total Latency: {latency_ms} ms")
        
        # Interpret the score based on your bucket mapping:
        if final_score >= 1.0:
            rating = "Excellent"
        elif final_score >= 0.75:
            rating = "Good"
        elif final_score >= 0.5:
            rating = "Acceptable"
        elif final_score > 0.0:
            rating = "Poor"
        else:
            rating = "No python files found or files had critical issues (score 0.0)"
            
        print(f"Rating: **{rating}**")
        
    else:
        print(f"❌ Analysis Failed. Latency: {latency_ms} ms")