"""Small heuristics to detect whether a README contains real metrics.

The primary use is to detect whether a model README contains evaluation
results or benchmark tables (accuracy / F1 / BLEU / perplexity, etc.).
The heuristics are intentionally conservative and tuned for README-like
content rather than arbitrary pages.
"""

from __future__ import annotations

import re
from typing import List


# ----------------- helpers -----------------
_METRIC_WORDS = [
    "accuracy", "acc", "f1", "f1-score", "precision", "recall", "auc", "auroc",
    "bleu", "rouge", "meteor", "ter", "chrf", "mse", "rmse", "mae", "r2", "perplexity",
    "wer", "cer", "map", "mrr", "ndcg", "exact match", "em", "top-1", "top-5",
    "glue", "squad", "librispeech", "common voice", "wmt", "imagenet", "superglue",
]

_PLACEHOLDER_WORDS = [
    "more information needed", "tbd", "coming soon", "todo", "n/a", "none",
]

# numbers like 92, 92.3, 0.923, 92%
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%?\b")

# reject obvious dates/versions (simple filter; we still require metric-word proximity)
_DATE_VER_RE = re.compile(r"(\b20\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\bv?\d+(?:\.\d+){1,}\b)")


def has_real_metrics(text: str) -> bool:
    """Return True if the text likely contains real evaluation metrics."""
    return _has_real_metrics(text)


def _has_real_metrics(text: str) -> bool:
    t = text.lower()

    # 1) YAML model-index with numeric value
    if ("model-index" in t and "metrics:" in t and
            re.search(r"\bvalue\s*:\s*[-+]?\d+(?:\.\d+)?", t)):
        return True

    # 2) Short-circuit if placeholders appear in any evaluation-ish section
    if any(p in t for p in _PLACEHOLDER_WORDS):
        # still allow model-index override above; otherwise 0
        pass

    # 3) Look inside "evaluation/results/benchmark" sections if present
    sections = _extract_eval_like_sections(t)

    # If no explicit section, just scan the whole text with proximity rule
    if not sections:
        sections = [t]

    # Proximity rule: metric word within ~100 chars of a number
    WINDOW = 100
    for s in sections:
        if any(p in s for p in _PLACEHOLDER_WORDS):
            # If the section is a placeholder, ignore it
            continue

        # quick reject: if there are no numbers at all, skip
        if not _NUM_RE.search(s):
            continue

        # proximity scan
        for m in _NUM_RE.finditer(s):
            num_start = m.start()
            # ignore obvious dates/versions near the number (heuristic)
            if _DATE_VER_RE.search(s[max(0, num_start - 10):num_start + 10]):
                continue

            left = max(0, num_start - WINDOW)
            right = min(len(s), num_start + WINDOW)
            window = s[left:right]

            if any(w in window for w in _METRIC_WORDS):
                return True

        # 4) Markdown table heuristic: header with metric-ish words + numeric cells
        if _looks_like_metric_table(s):
            return True

    return False


def _extract_eval_like_sections(t: str) -> List[str]:
    """Split by markdown headings and return bodies for evaluation-like headings."""
    parts = re.split(r"\n(?=#{1,6}\s)", t)  # split on headings
    out: List[str] = []
    for part in parts:
        # grab heading line
        first_line = part.splitlines()[0] if part else ""
        if re.search(r"\b(evaluation|results?|benchmarks?|performance|metrics?)\b", first_line):
            out.append(part)
    return out


def _looks_like_metric_table(s: str) -> bool:
    """Heuristic: detect a markdown table with metric header and numeric cells."""
    # Find markdown tables
    tables = re.findall(r"(?:\n\|.*\|\n\|[-:\s|]+\|\n(?:\|.*\|\n)+)", s)
    for tbl in tables:
        header = tbl.splitlines()[1] if len(tbl.splitlines()) >= 2 else ""
        if any(w in header for w in _METRIC_WORDS):
            # any numeric in body?
            body = "\n".join(tbl.splitlines()[2:])
            if _NUM_RE.search(body):
                return True
    return False
