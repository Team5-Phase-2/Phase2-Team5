# metrics/utils.py
import requests
from scoring import _hf_model_id_from_url

def fetch_hf_readme_text(model_url: str) -> str:
    """Fetch raw README.md text from a Hugging Face model repo."""
    try:
        model_id = _hf_model_id_from_url(model_url)  
        owner, repo = model_id.split("/", 1)
        raw_url = f"https://huggingface.co/{owner}/{repo}/raw/main/README.md"
        r = requests.get(raw_url, timeout=10)
        if r.status_code == 200:
            return r.text or ""
        return ""
    except Exception:
        return ""

