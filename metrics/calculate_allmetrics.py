import time
from __ import RampUpTimeMetric
from __ import BusFactorMetric
from __ import LicenseMetric
from __ import PerformanceClaimsMetric
from __ import SizeMetric
from __ import DatasetCodeMetric
from __ import DatasetQualityMetric
from __ import CodeQualityMetric
from typing import Dict


def calculate_all_metrics(model_url: str) -> Dict[str, MetricResult]:
    results = {
        "ramp_up_time": RampUpTimeMetric(model_url),
        "bus_factor": BusFactorMetric(model_url),
        "license": LicenseMetric(model_url),
        "performance_claims": PerformanceClaimsMetric(model_url),
        "size_score": SizeMetric(model_url),
        "dataset_and_code_score": DatasetCodeMetric(model_url),
        "dataset_quality": DatasetQualityMetric(model_url),
        "code_quality": CodeQualityMetric(model_url),
    }

    return results