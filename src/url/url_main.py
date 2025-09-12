# src/url_main.py
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
