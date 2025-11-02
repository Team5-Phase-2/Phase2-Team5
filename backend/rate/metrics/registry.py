# metrics/registry.py
from .ramp_up_time import ramp_up_time
from .bus_factor import bus_factor
from .license_score import license_score
from .performance_claims import performance_claims
from .size_score import size_score
from .dataset_code import dataset_and_code_score
from .dataset_quality import dataset_quality
from .code_quality import code_quality

# list of (metric_key, metric_function)
METRIC_REGISTRY = [
    ("ramp_up_time", ramp_up_time),
    ("bus_factor", bus_factor),
    ("license", license_score),
    ("performance_claims", performance_claims),
    ("size_score", size_score),
    ("dataset_and_code_score", dataset_and_code_score),
    ("dataset_quality", dataset_quality),
    ("code_quality", code_quality),
]
