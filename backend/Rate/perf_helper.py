"""backend.Rate.perf_helper

Heuristics for detecting whether a repository or README contains
performance/metric claims. Used by scoring/metric modules to determine if a
model advertises quantitative results.

The functions in this module are intentionally lightweight text heuristics
that operate on raw README or file text; they do not call external services.
"""

import re

# ----------------- helpers -----------------

# Words commonly used to indicate metrics or evaluation names.
_METRIC_WORDS = [
    "accuracy", "acc", "f1", "f1-score", "precision", "recall", "auc", "auroc",
    "bleu", "rouge", "meteor", "ter", "chrf", "mse", "rmse", "mae", "r2", "perplexity",
    "wer", "cer", "map", "mrr", "ndcg", "exact match", "em", "top-1", "top-5",
    "glue", "squad", "librispeech", "common voice", "wmt", "imagenet", "superglue",
]

# Placeholder phrases that indicate metrics are not present yet.
_PLACEHOLDER_WORDS = ["more information needed", "tbd", "coming soon", "todo", "n/a", "none"]

# Regular expressions used by the heuristics
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%?\b")  # numbers like 92, 92.3, 0.923, 92%
_DATE_VER_RE = re.compile(r"(\b20\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\bv?\d+(?:\.\d+){1,}\b)")

# reject obvious dates/versions (simple filter; we still require metric-word proximity)
_DATE_VER_RE = re.compile(
    r"(\b20\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\bv?\d+(?:\.\d+){1,}\b)"
)

def has_real_metrics(text: str) -> bool:
    """Public wrapper that returns whether the provided text contains
    plausible metric values paired with metric names.

    Args:
        text: Raw text (README, config, etc.) to inspect.

    Returns:
        True if heuristics detect metric-like content; False otherwise.
    """

    return _has_real_metrics(text)


def _has_real_metrics(text: str) -> bool:
    """Internal implementation of the metric-detection heuristics."""

    t = text.lower()

    # 1) If a model-index YAML contains numeric metrics use that as a positive
    # signal (explicit structured metadata trumps heuristics).
    if ("model-index" in t and "metrics:" in t and re.search(r"\bvalue\s*:\s*[-+]?\d+(?:\.\d+)?", t)):
        return True

    # 2) If placeholder phrases appear in evaluation sections, treat them as
    # not-yet-provided and continue scanning other parts.
    if any(p in t for p in _PLACEHOLDER_WORDS):
        pass

    # 3) Prefer examining explicit evaluation-like sections if present.
    sections = _extract_eval_like_sections(t)

    # If no explicit section, just scan the whole text with proximity rule
    if not sections:
        sections = [t]

    # Proximity rule: a metric word should appear near a numeric token.
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
            # Skip obvious dates/versions near numbers
            if _DATE_VER_RE.search(s[max(0, num_start - 10):num_start + 10]):
                continue

            left = max(0, num_start - WINDOW)
            right = min(len(s), num_start + WINDOW)
            window = s[left:right]

            if any(w in window for w in _METRIC_WORDS):
                return True

        # 4) Markdown table heuristic: header contains metric words and body has numbers
        if _looks_like_metric_table(s):
            return True

    return False


def _extract_eval_like_sections(t: str) -> list[str]:
    """Return sections of text whose headings indicate evaluation/results.

    Splits text on markdown headings and returns parts whose heading line
    matches evaluation/benchmark/performance keywords.
    """

    parts = re.split(r"\n(?=#{1,6}\s)", t)
    out = []
    for part in parts:
        # grab heading line
        first_line = part.splitlines()[0] if part else ""
        if re.search(r"\b(evaluation|results?|benchmarks?|performance|metrics?)\b", first_line):
            out.append(part)
    return out


def _looks_like_metric_table(s: str) -> bool:
    """Heuristic to detect markdown tables that contain metric values."""

    tables = re.findall(r"(?:\n\|.*\|\n\|[-:\s|]+\|\n(?:\|.*\|\n)+)", s)
    for tbl in tables:
        header = tbl.splitlines()[1] if len(tbl.splitlines()) >= 2 else ""
        if any(w in header for w in _METRIC_WORDS):
            # any numeric in body?
            body = "\n".join(tbl.splitlines()[2:])
            if _NUM_RE.search(body):
                return True
    return False