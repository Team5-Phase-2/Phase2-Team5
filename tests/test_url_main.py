# tests/test_url_main.py
import io
import os
import json
import runpy
import types
import pathlib
import pytest

# We’ll patch these with fakes to avoid network and keep stdout clean
class _FakeRouter:
    def route(self, urls_iter):
        # url_main calls route(iter([url])) per URL
        for u in urls_iter:
            u = (u or "").strip()
            if not u:
                continue
            # Yield a "model" item; writer now accepts raw strings
            yield u

class _FakeWriter:
    def __init__(self, out=None):
        self.count = 0
    def write(self, item):
        # Emit a minimal valid NDJSON line using just the URL tail as name
        self.count += 1
        url = item if isinstance(item, str) else getattr(item, "model_url", "")
        name = url.rsplit("/", 1)[-1] if "/" in url else url
        rec = {
            "name": name or "",
            "category": "MODEL",
            "net_score": 0.0, "net_score_latency": 0,
            "ramp_up_time": 0.0, "ramp_up_time_latency": 0,
            "bus_factor": 0.0, "bus_factor_latency": 0,
            "performance_claims": 0.0, "performance_claims_latency": 0,
            "license": 0.0, "license_latency": 0,
            "size_score": {"raspberry_pi":0.0,"jetson_nano":0.0,"desktop_pc":0.0,"aws_server":0.0},
            "size_score_latency": 0,
            "dataset_and_code_score": 0.0, "dataset_and_code_score_latency": 0,
            "dataset_quality": 0.0, "dataset_quality_latency": 0,
            "code_quality": 0.0, "code_quality_latency": 0,
        }
        sys_stdout = __import__("sys").stdout
        sys_stdout.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=True) + "\n")
        sys_stdout.flush()

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    # Keep env predictable per test
    for k in ("LOG_FILE", "LOG_LEVEL", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    # Avoid accidental network noise vars
    monkeypatch.setenv("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "1")
    monkeypatch.setenv("HF_HUB_ENABLE_HF_TRANSFER", "0")
    yield

def _patch_router_writer(monkeypatch):
    import src.url.url_main as url_main
    monkeypatch.setattr(url_main, "UrlRouter", _FakeRouter)
    monkeypatch.setattr(url_main, "NdjsonWriter", _FakeWriter)

def test_iter_urls_from_file_trims_and_skips_blanks(tmp_path):
    from src.url.url_main import iter_urls_from_file
    p = tmp_path / "urls.txt"
    p.write_text("\n  https://a/b \n\nhttps://c/d\n", encoding="utf-8")
    got = list(iter_urls_from_file(str(p)))
    assert got == ["https://a/b", "https://c/d"]

def test_validate_env_prints_on_invalid_token(capsys, monkeypatch):
    from src.url.url_main import validate_env, setup_logging
    monkeypatch.setenv("GITHUB_TOKEN", "not_ghp_token")
    log = setup_logging()  # default: no file logging
    validate_env(log)
    err = capsys.readouterr().err
    assert "Invalid GitHub token provided" in err

def test_setup_logging_bad_path_exits(monkeypatch):
    from src.url.url_main import setup_logging
    # Make LOG_FILE a directory to trigger OSError in FileHandler or open()
    monkeypatch.setenv("LOG_FILE", "/proc/does/not/exist/l.log")
    monkeypatch.setenv("LOG_LEVEL", "1")
    with pytest.raises(SystemExit):
        _ = setup_logging()

def test_process_urls_emits_one_line_per_model(monkeypatch, capsys):
    from src.url.url_main import _process_urls, setup_logging
    _patch_router_writer(monkeypatch)
    logger = setup_logging()
    urls = ["https://huggingface.co/owner/m1", "https://huggingface.co/owner/m2"]
    errs = _process_urls(urls, logger)
    out = capsys.readouterr().out.strip().splitlines()
    assert errs == 0
    assert len(out) == 2  # one NDJSON line per URL
    # minimal schema sanity
    rec0 = json.loads(out[0])
    assert rec0["category"] == "MODEL"
    assert "size_score" in rec0


def test_run_url_file_missing_returns_1(tmp_path, monkeypatch, capsys):
    from src.url.url_main import run_url_file
    rc = run_url_file(str(tmp_path / "nope.txt"))
    assert rc == 1
    assert "fatal: URL file not found" in capsys.readouterr().err

def test_run_url_file_success_happy_path(tmp_path, monkeypatch, capsys):
    from src.url.url_main import run_url_file
    # patch router/writer to fast fakes
    _patch_router_writer(monkeypatch)
    urlfile = tmp_path / "urls.txt"
    urlfile.write_text("https://huggingface.co/owner/m1\nhttps://huggingface.co/owner/m2\n")
    rc = run_url_file(str(urlfile))
    assert rc == 0
    out_lines = capsys.readouterr().out.strip().splitlines()
    assert len(out_lines) == 2
    # valid JSON lines
    for ln in out_lines:
        rec = json.loads(ln)
        assert rec["category"] == "MODEL"
        assert isinstance(rec["size_score"], dict)

def test_fallback_line_uses_model_id_when_parsable(capsys):
    from src.url.url_main import _fallback_line
    # Valid HF model URL → should canonicalize to "owner/repo"
    _fallback_line("https://huggingface.co/google-bert/bert-base-uncased")
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) >= 1
    rec = json.loads(out[-1])
    assert rec["name"] == "google-bert/bert-base-uncased"
    assert rec["category"] == "MODEL"

def test_fallback_line_uses_raw_value_on_exception(capsys):
    from src.url.url_main import _fallback_line
    # Pass a value that will make _hf_model_id_from_url raise → falls back to raw
    _fallback_line(None)  # type: ignore[arg-type]
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) >= 1
    rec = json.loads(out[-1])
    assert rec["name"] is None  # raw value echoed because parsing failed
    assert rec["category"] == "MODEL"
