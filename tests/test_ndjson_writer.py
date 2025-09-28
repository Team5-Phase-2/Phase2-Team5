# tests/test_ndjson_writer.py
import io
import json
from types import SimpleNamespace
import pytest

# ---- Fakes for metrics (no network) -----------------------------------------

class _FakeMetric:
    def __init__(self, score, latency_ms):
        self._score = score
        self._lat = latency_ms
    def calculate(self, url):
        # return object with .score and .latency_ms like your real metrics
        return SimpleNamespace(score=self._score, latency_ms=self._lat)

class _FakeCalc:
    """Matches shape used by NdjsonWriter: .metrics[...] with calculate()."""
    def __init__(self):
        self.metrics = {
            "ramp_up_time": _FakeMetric(1.0, 100),
            "bus_factor": _FakeMetric(0.6, 200),
            "license": _FakeMetric(0.5, 300),
            "size_score": _FakeMetric(0.25, 400),   # has_size=True, desktop_pc=0.25
            "code_quality": _FakeMetric(0.75, 500),
            # dataset_* not called by writer; remain defaults
        }

class _FakePerf:
    def calculate(self, url):
        return SimpleNamespace(score=1.0, latency_ms=150)  # 0 or 1 depending on your impl

# ---- Helpers ----------------------------------------------------------------

def _patch_metrics(monkeypatch, *, calc=_FakeCalc, perf=_FakePerf):
    import src.url.ndjson_writer as nw
    monkeypatch.setattr(nw, "MetricsCalculator", calc)
    monkeypatch.setattr(nw, "PerformanceClaimsMetric", perf)

def _parse_single_line(buf: io.StringIO):
    data = buf.getvalue()
    # exactly one newline-terminated line
    assert data.endswith("\n")
    lines = data.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])

# ---- Tests ------------------------------------------------------------------

def test_writer_basic_fields_and_math(monkeypatch):
    _patch_metrics(monkeypatch)

    from src.url.ndjson_writer import NdjsonWriter
    out = io.StringIO()
    w = NdjsonWriter(out=out)

    url = "https://huggingface.co/google-bert/bert-base-uncased"
    w.write(url)

    rec = _parse_single_line(out)

    # name & category
    assert rec["name"] == "bert-base-uncased"
    assert rec["category"] == "MODEL"

    # scores present
    for k in ("ramp_up_time","bus_factor","license","code_quality","performance_claims"):
        assert isinstance(rec[k], float)

    # size_score present with all devices
    for dev in ("raspberry_pi","jetson_nano","desktop_pc","aws_server"):
        assert dev in rec["size_score"]

    # net_score — with your current averaging (writer includes many parts)
    parts = [
        rec["ramp_up_time"],
        rec["license"],
        rec["size_score"]["desktop_pc"],
        rec["bus_factor"],
        rec["performance_claims"],
        rec["dataset_and_code_score"],
        rec["dataset_quality"],
        rec["code_quality"],
    ]
    expected = round(sum(parts) / len(parts), 3) if parts else 0.0
    assert rec["net_score"] == expected

    # net_score_latency is the sum of all *_latency (except itself)
    latency_keys = [k for k in rec if k.endswith("_latency") and k != "net_score_latency"]
    expected_latency = sum(int(rec.get(k, 0) or 0) for k in latency_keys)
    assert rec["net_score_latency"] == expected_latency

def test_writer_accepts_object_with_model_url(monkeypatch):
    _patch_metrics(monkeypatch)

    from src.url.ndjson_writer import NdjsonWriter
    out = io.StringIO()
    w = NdjsonWriter(out=out)

    class Obj: pass
    o = Obj()
    o.model_url = "https://huggingface.co/google-bert/bert-base-uncased"

    w.write(o)
    rec = _parse_single_line(out)
    assert rec["name"] == "bert-base-uncased"
    assert rec["category"] == "MODEL"

def test_writer_still_emits_on_metric_exception(monkeypatch):
    # Make code_quality.calculate raise; writer should still emit a line.
    class _RaisingMetric(_FakeMetric):
        def calculate(self, url):
            raise RuntimeError("boom")

    class _CalcWithRaise(_FakeCalc):
        def __init__(self):
            super().__init__()
            self.metrics["code_quality"] = _RaisingMetric(0.0, 0)

    _patch_metrics(monkeypatch, calc=_CalcWithRaise)

    from src.url.ndjson_writer import NdjsonWriter
    out = io.StringIO()
    w = NdjsonWriter(out=out)

    w.write("https://huggingface.co/google-bert/bert-base-uncased")
    rec = _parse_single_line(out)

    # We still get a valid record; code_quality stays default 0.0 and latency coerced to int
    assert rec["name"] == "bert-base-uncased"
    assert rec["category"] == "MODEL"
    assert isinstance(rec["code_quality_latency"], int)
    assert rec["code_quality"] in (0.0, pytest.approx(0.0))

def test_writer_outputs_strict_ndjson(monkeypatch):
    _patch_metrics(monkeypatch)

    from src.url.ndjson_writer import NdjsonWriter
    out = io.StringIO()
    w = NdjsonWriter(out=out)

    w.write("https://huggingface.co/google-bert/bert-base-uncased")
    raw = out.getvalue()

    # One line, ends with newline, and parseable as JSON
    assert raw.endswith("\n")
    json.loads(raw.splitlines()[0])  # no exception
