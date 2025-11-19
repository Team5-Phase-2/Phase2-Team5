"""backend.Rate.metrics.code_quality

Estimate code quality by linting Python example files with pylint and
mapping pylint scores into a small normalized scale.
"""

from typing import Optional, Tuple
import time, tempfile, subprocess, sys, os, requests
from scoring import _hf_model_id_from_url


def code_quality(model_url: str) -> Tuple[Optional[float], int]:
    """Return (score, latency_ms) assessing repository code quality.

    The function attempts to fetch Python example files from the model
    repository and run `pylint` on them (requires `pylint` available in the
    execution environment). Pylint numeric scores are mapped to discrete
    buckets that are easier to combine with other metrics.
    """

    start_ns = time.time_ns()
    try:
        model_id = _hf_model_id_from_url(model_url)
        api_url = f"https://huggingface.co/api/models/{model_id}"
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            return None, (time.time_ns() - start_ns) // 1_000_000

        metadata = response.json()
        files_data = metadata.get("siblings", [])
        config = metadata.get("config", {})

        # Collect Python files present in the repository
        python_files = [f["rfilename"] for f in files_data if f.get("rfilename", "").endswith(".py")]

        scores = []
        if python_files:
            for python_file in python_files:
                file_url = f"https://huggingface.co/{model_id}/raw/main/{python_file}"
                file_response = requests.get(file_url, timeout=10)
                if file_response.status_code == 200:
                    sc = _analyze_with_pylint(file_response.text, python_file)
                    if sc is not None:
                        scores.append(sc)
        else:
            # Fallback: attempt to lint a reference modeling file for the model type
            model_type = config.get("model_type")
            if model_type:
                if model_type.endswith("_text"):
                    model_type = model_type.replace("_text", "")
                base_url = (
                    "https://raw.githubusercontent.com/huggingface/"
                    "transformers/main/src/transformers/models"
                )
                model_file = f"{base_url}/{model_type}/modeling_{model_type}.py"
                file_response = requests.get(model_file, timeout=10)
                if file_response.status_code == 200:
                    sc = _analyze_with_pylint(file_response.text, f"modeling_{model_type}.py")
                    if sc is not None:
                        scores.append(sc)

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
