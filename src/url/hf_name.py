# src/url/hf_name.py
from urllib.parse import urlparse, unquote

def hf_model_repo_name(u: str) -> str:
    """
    Return just the repo name (last model segment) for HF model links or org/name strings.
    Examples:
      https://huggingface.co/google-bert/bert-base-uncased        -> bert-base-uncased
      https://huggingface.co/google-bert/bert-base-uncased/       -> bert-base-uncased
      https://huggingface.co/google-bert/bert-base-uncased/tree/main -> bert-base-uncased
      google-bert/bert-base-uncased                               -> bert-base-uncased
      bert-base-uncased                                           -> bert-base-uncased
    """
    s = u.strip()
    # handle plain "org/name" or "name"
    if "://" not in s and not s.startswith("huggingface.co/"):
        parts = [p for p in s.split("/") if p]
    else:
        p = urlparse(s)
        parts = [p for p in p.path.split("/") if p]

    if not parts:
        return ""
    # ignore listing prefixes if they slip in
    if parts[0] in {"models", "spaces", "datasets", "docs", "organizations", "tasks"} and len(parts) >= 2:
        name = parts[1]
    elif len(parts) >= 2:
        name = parts[1]          # /org/name[/...]
    else:
        name = parts[0]          # /name
    name = unquote(name)
    return name[:-4] if name.endswith(".git") else name
