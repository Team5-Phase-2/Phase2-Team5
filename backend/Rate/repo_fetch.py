"""backend.Rate.repo_fetch

Utilities to fetch a small subset of files from a Hugging Face repository's
raw endpoints. Useful for heuristics that inspect README, license, or
configuration files without using the HF API.

Provides:
- `download_hf_repo_subset(model_url: str, candidates: list[str] | None) -> Path`:
    Download common candidate files (README, LICENSE, etc.) into a temporary
    directory and return its path.
- `read_text_if_exists(dirpath: Path, name: str) -> str`: Safely read a text
    file from a directory if present, returning an empty string on error.
"""

# src/repo_fetch.py
from __future__ import annotations
from pathlib import Path
import tempfile
import requests
from scoring import _hf_model_id_from_url

# Candidate raw URLs to try (main/master)
_CANDIDATES = [
    "README.md",
    "README.yaml",
    "model_index.json",
    "config.json",
    "LICENSE",
    "LICENSE.txt",
    "COPYING",
]

def download_hf_repo_subset(model_url: str, candidates: list[str] | None = None) -> Path:
    """
    Download a handful of common files from HF repo raw endpoints into a temp dir.
    Returns the directory path containing whatever was fetched.
    (No Hugging Face API is used; only raw file HTTP.)
    """
    model_id = _hf_model_id_from_url(model_url)  # "owner/repo"
    owner, repo = model_id.split("/", 1)

    files = candidates or _CANDIDATES
    tmp = Path(tempfile.mkdtemp(prefix="hf_repo_"))

    for fname in files:
        for branch in ("main", "master"):
            url = f"https://huggingface.co/{owner}/{repo}/raw/{branch}/{fname}"
            try:
                r = requests.get(url, timeout=8)
                if r.status_code == 200 and r.text:
                    p = tmp / fname
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(r.text, encoding="utf-8")
                    break  # got this file; try next fname
            except Exception:
                # try next branch / file; continue silently
                pass

    return tmp

def read_text_if_exists(dirpath: Path, name: str) -> str:
    """Read a text file from `dirpath` if it exists, else return empty string.

    Args:
        dirpath (Path): Directory where file was downloaded.
        name (str): Filename to read.

    Returns:
        str: File contents or an empty string on error/not found.
    """

    path = dirpath / name
    if path.exists():
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            # Read errors gracefully degrade to empty string
            return ""
    return ""
