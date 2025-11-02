# metrics/dataset_quality.py
from typing import Optional, Tuple
import time, requests, re
from scoring import _hf_model_id_from_url
from .utils import fetch_hf_readme_text

def dataset_quality(model_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        model_id = _hf_model_id_from_url(model_url)
        readme = fetch_hf_readme_text(model_id) or ""
        if not readme.strip():
            return 0.0, (time.time_ns() - start_ns) // 1_000_000

        text = readme
        low = text.lower()

        api_ds = []
        try:
            api = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if api.status_code == 200:
                info = api.json()
                card = info.get("cardData") or {}
                ds = card.get("datasets") or []
                if isinstance(ds, list):
                    api_ds = [str(x).lower() for x in ds if x]
        except Exception:
            pass

        sec = None
        for pat in (
            r"(?ims)^[ \t]*#{1,6}[ \t]*(dataset|datasets)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
            r"(?ims)^[ \t]*#{1,6}[ \t]*(training data|pre[- ]?training data|pre[- ]?trained on|data|corpus)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
        ):
            m = re.search(pat, text)
            if m:
                sec = m.group(2)
                break
        section = (sec or text).lower()

        trusted = {
            "bookcorpus", "wikipedia", "openwebtext", "common crawl", "c4", "pile",
            "imagenet", "coco", "librispeech", "laion", "squad", "squad v2", "mnist",
            "cifar-10", "cifar10",
        }

        found_names = set()
        for name in trusted:
            if name in section or name in api_ds:
                found_names.add(name)

        quality_kw = (
            "dedup", "de-dup", "de-duplicate", "remove duplicates",
            "filter", "filtered", "quality filter",
            "balanced", "class balance", "stratified",
            "train/val", "train/valid", "train/test", "validation set", "evaluation set",
            "data cleaning", "preprocessing",
        )
        quality_hits = sum(1 for kw in quality_kw if kw in section)
        quality_frac = min(1.0, quality_hits / 4.0)

        if {"bookcorpus", "wikipedia"}.issubset(found_names):
            base = 0.9
            score = min(1.0, base + 0.05 + 0.05 * quality_frac)
        elif len(found_names) >= 2:
            base = 0.8
            score = min(0.95, base + 0.15 * quality_frac)
        elif len(found_names) == 1:
            base = 0.6
            score = min(0.9, base + 0.3 * quality_frac)
        elif api_ds or sec:
            base = 0.4
            score = min(0.7, base + 0.3 * quality_frac)
        else:
            score = 0.0

        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return round(float(score), 3), latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
