# src/url/ndjson_writer.py
import sys, json
from typing import TextIO
from urllib.parse import urlparse, unquote
from src.url.router import ModelItem
from src.metrics_framework import MetricsCalculator, PerformanceClaimsMetric

def hf_model_repo_name(url: str) -> str:
    parts = [s for s in urlparse(url).path.split('/') if s]
    if not parts: return ""
    name = parts[0] if len(parts) == 1 else parts[1]
    return unquote(name[:-4] if name.endswith(".git") else name)

class NdjsonWriter:
    def __init__(self, out: TextIO | None = None) -> None:
        self.out = out or sys.stdout
        self.calc = MetricsCalculator()
        self.perf_metric = PerformanceClaimsMetric()

    def write(self, item: ModelItem) -> None:
        rec = {
            "name": hf_model_repo_name(item.model_url),
            "category": "MODEL",
            "net_score": 0.0, "net_score_latency": 0,
            "ramp_up_time": 0.0, "ramp_up_time_latency": 0,
            "bus_factor": 0.0, "bus_factor_latency": 0,
            "performance_claims": 0.0, "performance_claims_latency": 0,
            "license": 0.0, "license_latency": 0,
            "size_score": {"raspberry_pi": 0.0, "jetson_nano": 0.0, "desktop_pc": 0.0, "aws_server": 0.0},
            "size_score_latency": 0,
            "dataset_and_code_score": 0.0, "dataset_and_code_score_latency": 0,
            "dataset_quality": 0.0, "dataset_quality_latency": 0,
            "code_quality": 0.0, "code_quality_latency": 0,
        }
        has_size = False

        try:
            # ramp_up_time
            try:
                ru = self.calc.metrics["ramp_up_time"].calculate(item.model_url)
                if ru and ru.score is not None: rec["ramp_up_time"] = round(float(ru.score), 3)
                rec["ramp_up_time_latency"] = int(getattr(ru, "latency_ms", 0))
            except Exception:
                pass

            # bus_factor
            try:
                bf = self.calc.metrics["bus_factor"].calculate(item.model_url)
                if bf and bf.score is not None: rec["bus_factor"] = round(float(bf.score), 3)
                rec["bus_factor_latency"] = int(getattr(bf, "latency_ms", 0))
            except Exception:
                pass

            # license
            try:
                lic = self.calc.metrics["license"].calculate(item.model_url)
                if lic and lic.score is not None: rec["license"] = round(float(lic.score), 3)
                rec["license_latency"] = int(getattr(lic, "latency_ms", 0))
            except Exception:
                pass

            # size_score
            try:
                sz = self.calc.metrics["size_score"].calculate(item.model_url)
                if sz and sz.score is not None:
                    v = float(sz.score)
                    rec["size_score"] = {"raspberry_pi": v, "jetson_nano": v, "desktop_pc": v, "aws_server": v}
                    has_size = True
                rec["size_score_latency"] = int(getattr(sz, "latency_ms", 0))
            except Exception:
                pass

            # performance_claims
            try:
                pc = self.perf_metric.calculate(item.model_url)
                s = float(pc.score) if (pc and pc.score is not None) else 0.0
                rec["performance_claims"] = 1.0 if s >= 0.5 else 0.0
                rec["performance_claims_latency"] = int(getattr(pc, "latency_ms", 0))
            except Exception:
                pass

            # code_quality
            try:
                cq = self.calc.metrics["code_quality"].calculate(item.model_url)
                if cq and cq.score is not None: rec["code_quality"] = round(float(cq.score), 3)
                rec["code_quality_latency"] = int(getattr(cq, "latency_ms", 0))
            except Exception:
                pass

            # net_score from whatever you have
            try:
                parts, lats = [], []
                parts.append(float(rec.get("ramp_up_time", 0.0))); lats.append(int(rec.get("ramp_up_time_latency", 0)))
                parts.append(float(rec.get("license", 0.0)));     lats.append(int(rec.get("license_latency", 0)))
                if has_size:
                    parts.append(float(rec["size_score"]["desktop_pc"])); lats.append(int(rec.get("size_score_latency", 0)))
                rec["net_score"] = round(sum(parts) / len(parts), 3) if parts else 0.0
                rec["net_score_latency"] = max(lats) if lats else 0
            except Exception:
                pass

        finally:
            # strict, compact NDJSON, newline-terminated
            self.out.write(json.dumps(rec, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n')
            self.out.flush()
