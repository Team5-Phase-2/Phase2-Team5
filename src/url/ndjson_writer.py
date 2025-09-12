# src/url/ndjson_writer.py
from __future__ import annotations
import json
import sys
from typing import TextIO
from .router import ModelItem

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

class NdjsonWriter:
    def __init__(self, out: TextIO | None = None) -> None:
        self.out = out or sys.stdout

    def write(self, item: ModelItem) -> None:
        rec = dict(REQUIRED_RECORD_TEMPLATE)
        rec["name"] = item.model_url
        # these two fields are NOT required by the spec; kept to help later stages:
        rec["_linked_datasets"] = item.datasets
        rec["_linked_code"] = item.code
        self.out.write(json.dumps(rec) + "\n")
