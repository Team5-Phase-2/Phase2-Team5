# metrics/dataset_code.py
from typing import Optional, Tuple
import time, requests
from scoring import _hf_model_id_from_url
from .utils import fetch_hf_readme_text

def dataset_and_code_score(model_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return 0.0, (time.time_ns() - start_ns) // 1_000_000

        dataset_available = False
        code_available = False

        api = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
        if api.status_code == 200:
            info = api.json()
            card = info.get("cardData") or {}

            ds = card.get("datasets") or []
            if isinstance(ds, list) and ds:
                dataset_available = True

            for s in (info.get("siblings") or []):
                fn = (s.get("rfilename") or "").lower()
                if fn.endswith(".py"):
                    code_available = True
                    break

        if not code_available:
            readme = fetch_hf_readme_text(model_id)
            if readme:
                low = readme.lower()
                strong_python_signals = (
                    "```python",
                    "from transformers import",
                    "autotokenizer",
                    "automodel",
                    "pipeline(",
                    "pip install transformers",
                )
                if any(k in low for k in strong_python_signals):
                    code_available = True

        if dataset_available and code_available:
            score = 1.0
        elif dataset_available or code_available:
            score = 0.5
        else:
            score = 0.0

        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return 0.0, latency_ms
