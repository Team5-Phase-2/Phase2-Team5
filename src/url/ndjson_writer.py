# src/url/ndjson_writer.py

from __future__ import annotations
import json,os
import sys
from typing import TextIO
from src.url.hf_name import hf_model_repo_name
from src.url.router import ModelItem
from src.scoring import _hf_model_id_from_url
from src.metrics_framework import MetricsCalculator

from src.metrics_framework import PerformanceClaimsMetric

REQUIRED_RECORD_TEMPLATE = {
    "name": "",  # model name/url
    "category": "",
    "net_score": 0.0,
    "net_score_latency": 0,
    "ramp_up_time": 0.0, "ramp_up_time_latency": 0,
    "bus_factor": 0.0, "bus_factor_latency": 0,
    "performance_claims": 0.0, "performance_claims_latency": 0,
    "license": 0.0, "license_latency": 0,
    "size_score": {
        "raspberry_pi": 0.0,
        "jetson_nano": 0.0,
        "desktop_pc": 0.0,
        "aws_server": 0.0,
    },
    "size_score_latency": 0,
    "dataset_and_code_score": 0.0, "dataset_and_code_score_latency": 0,
    "dataset_quality": 0.0, "dataset_quality_latency": 0,
    "code_quality": 0.0, "code_quality_latency": 0,
}

#class NdjsonWriter:
#    def __init__(self, out: TextIO | None = None) -> None:
#        self.out = out or sys.stdout
#
#   def write(self, item: ModelItem) -> None:
#        rec = dict(REQUIRED_RECORD_TEMPLATE)
#        rec["name"] = item.model_url
#        # these two fields are NOT required by the spec; kept to help later stages:
#        rec["_linked_datasets"] = item.datasets
#        rec["_linked_code"] = item.code
#        self.out.write(json.dumps(rec) + "\n")
class NdjsonWriter:
    def __init__(self, out: TextIO | None = None) -> None:
        self.out = out or sys.stdout
        self.calc = MetricsCalculator()

        self.perf_metric = PerformanceClaimsMetric()

    def write(self, item) -> None:
        # 1) compute metrics (parallel + timed inside)
       # metrics = score_model(item.model_url, cache_dir=".cache_hf", parallelism=8)
        url = item if isinstance(item, str) else getattr(item, "model_url", "")
        url = (url or "").strip()
        # 2) build required record
        rec = dict(REQUIRED_RECORD_TEMPLATE)
        rec["name"] = hf_model_repo_name(url)  # canonical org/name
        #rec["name"] = "bert-base-uncased"
        rec["category"] = "MODEL"
        #rec.update(metrics)
       # ---- ramp_up_time: overwrite with our concrete metric ----
        try:
            ru_res = self.calc.metrics["ramp_up_time"].calculate(url)
            if ru_res.score is not None:
                rec["ramp_up_time"] = round(float(ru_res.score), 3)
            # always record latency we measured
            rec["ramp_up_time_latency"] = int(ru_res.latency_ms)
        except Exception:
            # keep whatever score_model produced; set latency to 0 if needed
            rec["ramp_up_time_latency"] = int(rec.get("ramp_up_time_latency", 0) or 0)

         # ---- bus_factor: overwrite with our concrete metric ----
        try:
            bf_res = self.calc.metrics["bus_factor"].calculate(url)
            if bf_res.score is not None:
                rec["bus_factor"] = round(float(bf_res.score), 3)
            rec["bus_factor_latency"] = int(bf_res.latency_ms)
        except Exception:
            # keep value from score_model if present; ensure latency key exists
            rec["bus_factor_latency"] = int(rec.get("bus_factor_latency", 0) or 0)


        # overwrite license with real metric (README -> license section)
        lic_res = self.calc.metrics["license"].calculate(url)
        rec["license"] = round(float(lic_res.score), 3)
        rec["license_latency"] = int(lic_res.latency_ms)

        sz_res = self.calc.metrics["size_score"].calculate(url)
        metric_obj = self.calc.metrics["size_score"]
        if getattr(metric_obj, "device_scores", None):
            rec["size_score"] = dict(metric_obj.device_scores)
        else:
            if sz_res.score is not None:
                sz = float(sz_res.score)
                rec["size_score"] = {
                    "raspberry_pi": sz, "jetson_nano": sz,
                    "desktop_pc": sz, "aws_server": sz,
                }
        has_size = (sz_res.score is not None)
        rec["size_score_latency"] = int(sz_res.latency_ms)

        # ---- performance_claims (standalone 0.0 or 1.0) ----

        try:
            pc_res = self.perf_metric.calculate(url)
            score = float(pc_res.score) if (pc_res and pc_res.score is not None) else 0.0
            # keep metric’s own value; just clamp and round
            score = max(0.0, min(1.0, score))
            rec["performance_claims"] = round(score, 3)
            rec["performance_claims_latency"] = int(pc_res.latency_ms or 0)
        except Exception:
            rec["performance_claims"] = 0.0
            rec["performance_claims_latency"] = 0


            # ---- code_quality metric ----
        try:
            cq_res = self.calc.metrics["code_quality"].calculate(url)
            if cq_res.score is not None:
                rec["code_quality"] = round(float(cq_res.score), 3)
            rec["code_quality_latency"] = int(cq_res.latency_ms)
        except Exception as e:
            # fallback: keep whatever is already there (default 0.0), set latency 0
            rec["code_quality_latency"] = int(rec.get("code_quality_latency", 0) or 0)

                # ---- dataset_and_code_score ----
        try:
            dac_res = self.calc.metrics["dataset_and_code_score"].calculate(url)
            if dac_res.score is not None:
                rec["dataset_and_code_score"] = round(float(dac_res.score), 3)
            rec["dataset_and_code_score_latency"] = int(dac_res.latency_ms)
        except Exception:
            rec["dataset_and_code_score_latency"] = int(rec.get("dataset_and_code_score_latency", 0) or 0)

        # ---- dataset_quality ----
        try:
            dq_res = self.calc.metrics["dataset_quality"].calculate(url)
            if dq_res.score is not None:
                rec["dataset_quality"] = round(float(dq_res.score), 3)
            rec["dataset_quality_latency"] = int(dq_res.latency_ms)
        except Exception:
            rec["dataset_quality_latency"] = int(rec.get("dataset_quality_latency", 0) or 0)



        # recompute net_score (preliminary averaging over finished metrics)
        try:
            parts = []
            latencies = []

            #ramp_up_time (dummy)
            parts.append(float(rec.get("ramp_up_time", 0.0)))
            latencies.append(int(rec.get("ramp_up_time_latency", 0) or 0))

            #license
            parts.append(float(rec.get("license", 0.0)))
            latencies.append(int(rec.get("license_latency", 0) or 0))

            #size ('None' if unknown)
            if has_size:
                parts.append(float(rec["size_score"]["desktop_pc"]))
                latencies.append(int(rec.get("size_score_latency", 0) or 0))

            #bus_factor
            parts.append(float(rec.get("bus_factor", 0.0)))
            latencies.append(int(rec.get("bus_factor_latency", 0) or 0))

            #perf_claim
            parts.append(float(rec.get("performance_claims", 0.0)))
            latencies.append(int(rec.get("performance_claims_latency", 0) or 0))

            #dataset and code
            parts.append(float(rec.get("dataset_and_code_score", 0.0)))
            latencies.append(int(rec.get("dataset_and_code_score_latency", 0) or 0))

            #dataset quality
            parts.append(float(rec.get("dataset_quality", 0.0)))
            latencies.append(int(rec.get("dataset_quality_latency", 0) or 0))

            #code quality
            parts.append(float(rec.get("code_quality", 0.0)))
            latencies.append(int(rec.get("code_quality_latency", 0) or 0))
    

            rec["net_score"] = round(sum(parts) / len(parts), 3) if parts else 0.0
            latency_keys = [k for k in rec.keys() if k.endswith('_latency') and k != 'net_score_latency']
            rec["net_score_latency"] = sum(int(rec.get(k, 0) or 0) for k in latency_keys)

        except Exception:
            pass # keep existing net_score if something odd happens
        
        # 4) print one NDJSON object
        self.out.write(json.dumps(rec, separators=(',',':'), ensure_ascii=True, allow_nan=False) + '\n')
        self.out.flush()
        