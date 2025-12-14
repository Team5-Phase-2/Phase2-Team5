# tests/test_metrics_registry.py

import sys
import types

# ===================================================================
# PRE-INJECT FAKE METRIC MODULES ONLY
# (NO scoring injection — critical!)
# ===================================================================

_INJECTED_MODULES = []

metric_modules = {
    "ramp_up_time": "ramp_up_time",
    "bus_factor": "bus_factor",
    "license_score": "license_score",
    "performance_claims": "performance_claims",
    "size_score": "size_score",
    "dataset_code": "dataset_and_code_score",
    "dataset_quality": "dataset_quality",
    "code_quality": "code_quality",
    "reviewedness": "reviewedness",
    "reproducibility": "reproducibility",
}

for module_name, func_name in metric_modules.items():
    module_path = f"backend.Rate.metrics.{module_name}"

    fake_mod = types.ModuleType(module_path)
    fake_mod.__dict__[func_name] = lambda *a, **k: (0.9, 5)

    sys.modules[module_path] = fake_mod
    _INJECTED_MODULES.append(module_path)

# ===================================================================
# NOW SAFE TO IMPORT REGISTRY
# ===================================================================
from backend.Rate.metrics.registry import METRIC_REGISTRY

# ===================================================================
# TESTS
# ===================================================================

def test_registry_length():
    assert len(METRIC_REGISTRY) == 10


def test_registry_entry_format():
    for key, fn in METRIC_REGISTRY:
        assert isinstance(key, str)
        assert key
        assert callable(fn)


def test_registry_keys_exact():
    expected = {
        "ramp_up_time",
        "bus_factor",
        "license",
        "performance_claims",
        "size_score",
        "dataset_and_code_score",
        "dataset_quality",
        "code_quality",
        "reviewedness",
        "reproducibility",
    }
    actual = {k for k, _ in METRIC_REGISTRY}
    assert actual == expected


def test_no_duplicate_keys():
    keys = [k for k, _ in METRIC_REGISTRY]
    assert len(keys) == len(set(keys))


# ===================================================================
# CLEANUP
# ===================================================================

def teardown_module(module):
    for name in _INJECTED_MODULES:
        sys.modules.pop(name, None)
