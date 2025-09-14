# src/url/ndjson_writer.py
"""
ndjson_writer.py
----------------

This module prints one JSON object (NDJSON line) for each ModelItem.

Classes:
- NdjsonWriter: writes ModelItem data to stdout (or any file-like object).

Behavior:
- Uses REQUIRED_RECORD_TEMPLATE to guarantee all fields exist
  (name, category, net_score, latencies, etc.)
- Currently fills everything with default values (0.0 or 0).
- Adds _linked_datasets and _linked_code to help teammates later,
  though these fields are not required by the spec.


Example output:
    {"name": "https://huggingface.co/google/gemma-3-270m",
     "category": "MODEL",
     "net_score": 0.0,
     "license": 0.0,
     ...,
     "_linked_datasets": ["https://huggingface.co/datasets/xlangai/AgentNet"],
     "_linked_code": ["https://github.com/SkyworkAI/Matrix-Game"]}
"""

from __future__ import annotations
import json
import sys
from typing import TextIO
from src.url.router import ModelItem
from src.scoring import score_model, _hf_model_id_from_url

REQUIRED_RECORD_TEMPLATE = {
    "name": "",  # model name/url
    "category": "MODEL",
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

    def write(self, item: ModelItem) -> None:
        # 1) compute metrics (parallel + timed inside)
        metrics = score_model(item.model_url, cache_dir=".cache_hf", parallelism=8)

        # 2) build required record
        rec = dict(REQUIRED_RECORD_TEMPLATE)
        rec["name"] = _hf_model_id_from_url(item.model_url)  # canonical org/name
        rec["category"] = "MODEL"
        rec.update(metrics)

        # 3) (optional) attach context fields the spec allows (“linked …”)
        if item.datasets:
            rec["linked_datasets"] = item.datasets
            # small “bonus” to dataset_and_code_score if links exist
            rec["dataset_and_code_score"] = max(rec["dataset_and_code_score"], 0.5)
        if item.code:
            rec["linked_code"] = item.code
            rec["dataset_and_code_score"] = max(rec["dataset_and_code_score"], 1.0 if item.datasets else 0.5)

        # 4) print one NDJSON object
        self.out.write(json.dumps(rec, ensure_ascii=True) + "\n")
        self.out.flush()