"""backend.Rate.metrics.utils

Small helpers used by metric implementations to fetch repository text and
resources. These helpers are intentionally simple and return empty strings on
transient errors to allow metrics to continue gracefully.
"""

import json
from os import environ
import ast
import math
import requests
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
    """
    Send a prompt to the Purdue GenAI chat completions API and return the response.
    """
    try:
        api_key = environ.get("PURDUE_GENAI_API_KEY")
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


def analyze_code(code: str) -> float:
    """
    Dependency-free code quality score (0.0 - 10.0)

    Uses static heuristics:
      - syntax validity
      - cyclomatic complexity
      - function length
      - docstring presence
      - risky API usage
      - too many globals
      - line length
      - unused imports (basic check)
    """

    # -----------------------------------------------------
    # 1. Syntax check
    # -----------------------------------------------------
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0.0

    score = 10.0

    # -----------------------------------------------------
    # 2. Compute metrics from AST
    # -----------------------------------------------------

    # Track metrics
    function_count = 0
    long_functions = 0
    missing_docstrings = 0
    complexity = 0
    globals_count = 0
    risky_calls = 0
    import_names = set()
    used_names = set()

    class Analyzer(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            nonlocal function_count, long_functions, missing_docstrings, complexity
            function_count += 1

            # docstring
            if ast.get_docstring(node) is None:
                missing_docstrings += 1
                complexity += 1

            # function length
            if hasattr(node, "body") and len(node.body) > 50:
                long_functions += 1
                complexity += math.log(len(node.body))

            # cyclomatic complexity (cheap)
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp)):
                    complexity += 1

            self.generic_visit(node)

        def visit_Global(self, node):
            nonlocal globals_count
            globals_count += len(node.names)

        def visit_Call(self, node):
            nonlocal risky_calls
            # detect eval/exec or other suspicious calls
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "compile"):
                risky_calls += 5
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                import_names.add(alias.asname or alias.name)

        def visit_ImportFrom(self, node):
            if node.module:
                import_names.add(node.module)

        def visit_Name(self, node):
            used_names.add(node.id)

    Analyzer().visit(tree)

    # -----------------------------------------------------
    # 3. Heuristics-based scoring
    # -----------------------------------------------------

    # Missing docstrings
    if function_count > 0:
        ratio = missing_docstrings / function_count
        score -= ratio * 3.0

    # Long functions
    score -= long_functions * 0.5

    # Complexity penalty
    score -= min(4.0, complexity * 0.1)

    # Risky calls
    score -= risky_calls * 0.5

    # Unused imports (simple heuristic)
    unused = [i for i in import_names if i not in used_names]
    score -= min(2.0, len(unused) * 0.25)

    # Line length penalties
    long_lines = sum(1 for line in code.splitlines() if len(line) > 120)
    score -= min(1.0, long_lines * 0.05)

    # Global usage
    score -= min(1.0, globals_count * 0.1)

    # Keep within 0–10
    score = max(0.0, min(10.0, score))
    return score / 10.0 
