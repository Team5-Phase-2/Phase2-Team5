import sys
import types

# ===================================================================
# PRE-INJECT FAKE METRIC MODULES so registry can import safely
# ===================================================================

# Real registry imports these exact module files and functions:
metric_modules = {
    "ramp_up_time": "ramp_up_time",
    "bus_factor": "bus_factor",
    "license_score": "license_score",
    "performance_claims": "performance_claims",
    "size_score": "size_score",
    "dataset_code": "dataset_and_code_score",   # <== IMPORTANT
    "dataset_quality": "dataset_quality",
    "code_quality": "code_quality",
    "reviewedness": "reviewedness",
    "reproducibility": "reproducibility",
}

for module_name, func_name in metric_modules.items():
    # Create module object
    fake_mod = types.ModuleType(f"backend.Rate.metrics.{module_name}")

    # Define the correct function the registry expects
    fake_func = lambda *a, **k: (0.9, 5)
    fake_mod.__dict__[func_name] = fake_func

    # Register module in sys.modules
    sys.modules[f"backend.Rate.metrics.{module_name}"] = fake_mod

# Stub scoring since some metric modules import it
fake_scoring = types.ModuleType("backend.Rate.scoring")
fake_scoring._hf_model_id_from_url = lambda x: "owner/repo"

# register both possible spellings
sys.modules["backend.Rate.scoring"] = fake_scoring
sys.modules["scoring"] = fake_scoring

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
