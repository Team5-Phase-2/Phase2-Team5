import sys
import types

# ===================================================================
# PRE-INJECT FAKE METRIC MODULES so registry can import safely
# ===================================================================

# Keep track of everything we inject so we can clean it up
_INJECTED_MODULES = []

metric_modules = {
    "ramp_up_time": "ramp_up_time",
    "bus_factor": "bus_factor",
    "license_score": "license_score",
    "performance_claims": "performance_claims",
    "size_score": "size_score",
    "dataset_code": "dataset_and_code_score",   # IMPORTANT
    "dataset_quality": "dataset_quality",
    "code_quality": "code_quality",
    "reviewedness": "reviewedness",
    "reproducibility": "reproducibility",
}

for module_name, func_name in metric_modules.items():
    module_path = f"backend.Rate.metrics.{module_name}"

    fake_mod = types.ModuleType(module_path)

    # Registry expects a callable metric function
    fake_mod.__dict__[func_name] = lambda *a, **k: (0.9, 5)

    sys.modules[module_path] = fake_mod
    _INJECTED_MODULES.append(module_path)

# -------------------------------------------------------------------
# Stub scoring (REQUIRED because some metric modules import it)
# -------------------------------------------------------------------
fake_scoring = types.ModuleType("backend.Rate.scoring")
fake_scoring._hf_model_id_from_url = lambda x: "owner/repo"

sys.modules["backend.Rate.scoring"] = fake_scoring
sys.modules["scoring"] = fake_scoring

_INJECTED_MODULES.extend([
    "backend.Rate.scoring",
    "scoring",
])

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
# CRITICAL: CLEANUP AFTER THIS FILE
# ===================================================================

def teardown_module(module):
    """
    Remove all fake modules injected by this test so they do not
    pollute later tests (especially test_scoring.py).
    """
    for name in _INJECTED_MODULES:
        sys.modules.pop(name, None)
