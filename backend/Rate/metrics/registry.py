"""backend.Rate.metrics.registry

Central registry of metric implementations. Each registry entry is a tuple
of `(metric_key, function)` where the function accepts a model URL and
returns `(score, latency_ms)` or `(None, latency_ms)` on failure.
"""

from .ramp_up_time import ramp_up_time
from .bus_factor import bus_factor
from .license_score import license_score
from .performance_claims import performance_claims
from .size_score import size_score
from .dataset_code import dataset_and_code_score
from .dataset_quality import dataset_quality
from .code_quality import code_quality
from .reviewedness import reviewedness
from ..reproducibility import reproducibility


# List of (metric_key, metric_function) consumed by the runner
METRIC_REGISTRY = [
    ("ramp_up_time", ramp_up_time),
    ("bus_factor", bus_factor),
    ("license", license_score),
    ("performance_claims", performance_claims),
    ("size_score", size_score),
    ("dataset_and_code_score", dataset_and_code_score),
    ("dataset_quality", dataset_quality),
    ("code_quality", code_quality),
    ("reviewedness", reviewedness),
    ("reproducibility", reproducibility),
]
