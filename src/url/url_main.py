# src/url_main.py
import os, sys, logging
from typing import Iterator
from src.url.router import UrlRouter
from src.url.ndjson_writer import NdjsonWriter

def setup_logging() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "0")
    log_path = os.getenv("LOG_FILE")

    logger = logging.getLogger("ece461")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)  # we’ll filter by handler’s level

    if not log_path:
        return logger  # no logging requested

    # Try to open the file; fail early if invalid path
    try:
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    except OSError:
        sys.stderr.write("Invalid log file path\n")
        sys.exit(1)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)

    # Map LOG_LEVEL → handler level
    if level == "0":
        # Touch file but write nothing
        open(log_path, "a").close()
        fh.setLevel(logging.CRITICAL + 1)  # effectively silence
    elif level == "1":
        fh.setLevel(logging.INFO)
    else:
        fh.setLevel(logging.DEBUG)

    logger.addHandler(fh)
    return logger

def validate_env(logger: logging.Logger) -> None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token and not (token.startswith("ghp_") or token.startswith("github_pat_")):
        # Don’t break stdout NDJSON; just log the problem
        logger.error("Invalid GitHub token provided")

def iter_urls_from_file(path: str) -> Iterator[str]:
    with open(path, "rt", encoding="utf-8") as f:
        for line in f:
            u = line.strip()
            if u:
                yield u

def run_url_file(url_file: str) -> int:
    logger = setup_logging()
    validate_env(logger)

    # Ensure we emit at least one INFO when LOG_LEVEL=1
    logger.info("Starting URL processing")

    router = UrlRouter()
    writer = NdjsonWriter()
    for item in router.route(iter_urls_from_file(url_file)):
        writer.write(item)
    logger.info("Finished URL processing")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m src.url_main /abs/path/to/URL_FILE", file=sys.stderr)
        sys.exit(1)
    sys.exit(run_url_file(sys.argv[1]))
