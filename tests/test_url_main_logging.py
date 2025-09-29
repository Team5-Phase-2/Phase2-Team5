# tests/test_url_main_logging.py
import os
import pathlib
import pytest

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("LOG_FILE", "LOG_LEVEL"):
        monkeypatch.delenv(k, raising=False)
    yield

def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def test_setup_logging_level_0_silences_output(tmp_path, monkeypatch):
    from src.url.url_main import setup_logging
    logp = tmp_path / "lvl0.log"
    logp.write_text("", encoding="utf-8")  # must exist
    monkeypatch.setenv("LOG_FILE", str(logp))
    monkeypatch.setenv("LOG_LEVEL", "0")

    logger = setup_logging()
    logger.debug("DBG")
    logger.info("INF")
    logger.error("ERR")  # even ERROR should be silenced by handler level CRITICAL+1

    txt = _read(logp)
    assert txt == ""  # handler was added but level filtered all records

def test_setup_logging_level_1_writes_info_not_debug(tmp_path, monkeypatch):
    from src.url.url_main import setup_logging
    logp = tmp_path / "lvl1.log"
    logp.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOG_FILE", str(logp))
    monkeypatch.setenv("LOG_LEVEL", "1")

    logger = setup_logging()
    logger.debug("DBG")
    logger.info("Hello INFO")

    txt = _read(logp)
    assert "INFO" in txt
    assert "Hello INFO" in txt
    assert "DEBUG" not in txt  # handler level is INFO

def test_setup_logging_level_2_writes_debug(tmp_path, monkeypatch):
    from src.url.url_main import setup_logging
    logp = tmp_path / "lvl2.log"
    logp.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOG_FILE", str(logp))
    monkeypatch.setenv("LOG_LEVEL", "2")

    logger = setup_logging()
    logger.debug("Hello DEBUG")

    txt = _read(logp)
    assert "DEBUG" in txt
    assert "Hello DEBUG" in txt
    # also touches the formatter line: it should include a timestamp/level/message pattern
    assert " " in txt and "ece461" not in txt  # basic sanity without overfitting

def test_setup_logging_unknown_level_defaults_to_debug(tmp_path, monkeypatch):
    from src.url.url_main import setup_logging
    logp = tmp_path / "lvltmp.log"
    logp.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOG_FILE", str(logp))
    monkeypatch.setenv("LOG_LEVEL", "weird")  # exercises .get(level_str, logging.DEBUG)

    logger = setup_logging()
    logger.debug("Fallback DEBUG")

    txt = _read(logp)
    assert "DEBUG" in txt
    assert "Fallback DEBUG" in txt
