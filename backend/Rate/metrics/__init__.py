"""backend.Rate.metrics

Package initialiser for metric implementations. Exposes the `METRIC_REGISTRY`
which modules can import to enumerate or register available metric checks.
"""

from .registry import METRIC_REGISTRY


# The package is intentionally small; individual metric modules live in the
# same directory and are imported by the registry when needed.
