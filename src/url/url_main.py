# src/url_main.py
"""
url_main.py
-----------

This is the entrypoint for handling a file of URLs.
It ties together classify.py, router.py, and ndjson_writer.py.

Functions:
- iter_urls_from_file(path: str) -> Iterator[str]
    Reads a file line by line and yields non-empty URLs.

- run_url_file(url_file: str) -> int
    Uses UrlRouter to group datasets/code with the next model,
    then NdjsonWriter to print one NDJSON line per model.
    Returns 0 on success.

Command-line usage:
    python -m src.url_main /abs/path/to/URL_FILE

Integration with ./run:
    When you call `./run URL_FILE` at the repo root,
    the run script calls run_url_file() with that file.
    Each MODEL URL in the file will produce exactly one JSON line
    with all required fields (stubbed with default values for now).
"""

from __future__ import annotations
import sys
from typing import Iterator
from src.url.router import UrlRouter
from src.url.ndjson_writer import NdjsonWriter

def iter_urls_from_file(path: str) -> Iterator[str]:
    with open(path, "rt", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u:
                yield u

def run_url_file(url_file: str) -> int:
    router = UrlRouter()
    writer = NdjsonWriter()
    for item in router.route(iter_urls_from_file(url_file)):
        writer.write(item)
    return 0

if __name__ == "__main__":
    # quick manual test: python -m src.url_main urls.txt
    if len(sys.argv) != 2:
        print("usage: python -m src.url_main /abs/path/to/URL_FILE", file=sys.stderr)
        sys.exit(1)
    sys.exit(run_url_file(sys.argv[1]))
