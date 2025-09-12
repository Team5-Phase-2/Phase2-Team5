#group datasets & code with the next model

# src/url/router.py

"""
router.py
---------

This module groups datasets and code with the next model URL.

Classes:
- ModelItem: a container (dataclass) holding one model URL plus any
  dataset/code URLs that came before it.
- UrlRouter: consumes a list of URLs, classifies them, and yields ModelItem
  objects for each model.

Logic:
- DATASET → stash in a list until a model appears
- CODE    → stash in a list until a model appears
- MODEL   → create a ModelItem with the stashed datasets and code, then clear
- UNKNOWN → log a warning (if LOG_LEVEL > 0)

Example:
    Input URLs:
        dataset1
        code1
        modelA
        code2
        modelB

    Output:
        ModelItem(modelA, datasets=[dataset1], code=[code1])
        ModelItem(modelB, datasets=[], code=[code2])
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
from typing import Iterable, Iterator, List
from .classify import classify

@dataclass
class ModelItem:
    model_url: str
    datasets: List[str] = field(default_factory=list)
    code: List[str] = field(default_factory=list)

class UrlRouter:
    def __init__(self) -> None:
        self._pending_ds: List[str] = []
        self._pending_code: List[str] = []

    def route(self, urls: Iterable[str]) -> Iterator[ModelItem]:
        """Consume a sequence of URLs and yield a ModelItem each time we see a MODEL."""
        for raw in urls:
            u = raw.strip()
            if not u:
                continue
            kind = classify(u)
            if kind == "DATASET":
                self._pending_ds.append(u)
            elif kind == "CODE":
                self._pending_code.append(u)
            elif kind == "MODEL":
                yield ModelItem(
                    model_url=u,
                    datasets=list(self._pending_ds),
                    code=list(self._pending_code),
                )
                self._pending_ds.clear()
                self._pending_code.clear()
            else:
                self._log(f"Unknown URL type, skipping: {u}", level=1)

    def _log(self, msg: str, level: int = 1) -> None:
        lvl = int(os.getenv("LOG_LEVEL", "0"))
        if level <= lvl:
            log_path = os.getenv("LOG_FILE")
            if log_path:
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(msg + "\n")
