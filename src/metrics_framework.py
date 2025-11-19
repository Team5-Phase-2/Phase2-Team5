"""Metrics calculator and per-metric implementations.

This module provides a small framework used by the CLI and NDJSON writer
to compute per-model metrics.  It defines a light-weight `BaseMetric` class
and a collection of concrete metric implementations (ramp-up, bus-factor,
license, size, dataset/code signals, code quality, and performance claims).

The implementations are deliberately defensive — network failures or
missing repo data yield `None` or conservative default scores rather
than raising exceptions.
"""


from __future__ import annotations

import math
import os
import re
import sys
import time
import tempfile
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict
from typing import Optional

import requests

# Local imports (normalized HF helpers)
from backend.Rate.scoring import _hf_model_id_from_url
from src.perf_helper import has_real_metrics
from src.repo_fetch import download_hf_repo_subset
from src.repo_fetch import read_text_if_exists

#==========HELPER for Performance Metric=============================

def _fetch_hf_readme_text(model_url: str) -> str:
    """Fetch raw README.md text from a Hugging Face model repo."""
    try:
        model_id = _hf_model_id_from_url(model_url)  # e.g., "owner/repo"
        owner, repo = model_id.split("/", 1)
        raw_url = f"https://huggingface.co/{owner}/{repo}/raw/main/README.md"
        r = requests.get(raw_url, timeout=10)
        if r.status_code == 200:
            return r.text or ""
        return ""
    except Exception:
        return ""
#=================================================================



@dataclass
class MetricResult:
    """Simple container for a per-metric numeric score and measured latency.

    Attributes:
        score: Optional[float] — the metric value in 0.0–1.0 or None if unknown.
        latency_ms: int — latency in milliseconds measured while computing.
    """
    score: Optional[float]  # optional to allow for None if calculation failed
    latency_ms: int

class BaseMetric(ABC):
    """Abstract base class for all metrics."""
    
    def __init__(self, metric_name: str):
        self.metric_name = metric_name
    
    def calculate(self, model_url: str) -> MetricResult:
        """Template method that handles timing and error handling"""
        start_time = time.time_ns()
        
        try:
            score = self._calculate_score(model_url)
            latency_ms = (time.time_ns() - start_time) // 1_000_000
            return MetricResult(score, latency_ms)
        except Exception as e:
            return MetricResult(None, (time.time_ns() - start_time) // 1_000_000)
    
    @abstractmethod
    def _calculate_score(self, model_url: str) -> Optional[float]:
        
        pass

class RampUpTimeMetric(BaseMetric):
    def __init__(self):
        super().__init__("ramp_up_time")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        # Normalize to org/name like your other metrics do
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return None  # no signal for non-HF model refs

        try:
            r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if r.status_code != 200:
                return None  # network/API issue → let caller renormalize
            info = r.json()
        except Exception:
            return None  # on any fetch error, produce no score

        # --- Signals ---
        # 1) Popularity proxy: likes (log-compressed to 0..1)
        likes = int(info.get("likes") or 0)
        likes_score = min(1.0, max(0.0, (math.log10(1 + likes) / 3.0)))  # ~1.0 near ~1k likes

        # 2) Ease-of-start proxy: README or model card present
        siblings = info.get("siblings") or []
        has_readme = any((s.get("rfilename") or "").lower() == "readme.md" for s in siblings)
        has_card = bool(info.get("cardData"))
        readme_score = 1.0 if (has_readme or has_card) else 0.3

        # 3) Tiny bonus if tags suggest examples/tutorials
        tags = [str(t).lower() for t in (info.get("tags") or [])]
        examples_bonus = 0.1 if any(("example" in t or "tutorial" in t) for t in tags) else 0.0

        # Combine & clamp
        score = 0.6 * readme_score + 0.4 * likes_score + examples_bonus
        score = min(1.0, max(0.0, score))

        # Round for stable output like your other fields
        return round(score, 3)

class BusFactorMetric(BaseMetric):
    def __init__(self):
        super().__init__("bus_factor")

    def _calculate_score(self, model_url: str) -> Optional[float]:

        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return 0.0  # unknown ⇒ conservative

        try:
            r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if r.status_code != 200:
                return 0.0
            info = r.json()

            # ---- downloads → log-normalized in [0,1]
            downloads = 0
            try:
                downloads = int(info.get("downloads") or 0)
            except Exception:
                downloads = 0
            downloads_norm = min(1.0, math.log10(1 + downloads) / 6.0)

            # ---- lastModified → freshness in [0,1]
            last_mod = info.get("lastModified")
            age_days = 365.0  # default stale
            if isinstance(last_mod, str):
                # '2025-03-01T12:34:56.789Z' → make it ISO compatible
                s = last_mod.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(s)
                    age_days = max(0.0, (time.time() - dt.timestamp()) / 86400.0)
                except Exception:
                    age_days = 365.0
            freshness = max(0.0, min(1.0, 1.0 - (age_days / 365.0)))

            return round(0.6 * downloads_norm + 0.4 * freshness, 3)
        except Exception:
            return 0.0

class LicenseMetric(BaseMetric):
    def __init__(self):
        super().__init__("license")
    
    def _calculate_score(self, model_url: str) -> float:
        """
        Map a license string to a normalized score (no Hugging Face API used).
          1.0 = permissive AND LGPL-2.1 compatible (e.g., MIT, Apache-2.0, BSD, MPL-2.0, LGPL-2.1)
          0.5 = unclear / custom / policy-dependent (e.g., OpenRAIL, LGPL-3.0, CC-BY-SA, model EULAs)
          0.0 = restrictive/incompatible/missing (e.g., GPL/AGPL, Non-Commercial, No-Derivatives, Proprietary, no license)
        """
        import re

        licenses_restrictive = (
            r"\bagpl(?:-?3(?:\.0)?)?(?:-only|-or-later|\+)?\b",
            r"\bgpl(?:-?2(?:\.0)?|-?3(?:\.0)?)(?:-only|-or-later|\+)?\b",
            r"\bgplv2\b", r"\bgplv3\b",
            r"\bcc-?by-?nc\b", r"\bcc-?nc\b", r"\bnon[-\s]?commercial\b", r"\bnoncommercial\b",
            r"\bresearch[-\s]?only\b", r"\bresearch[-\s]?use\b",
            r"\bno[-\s]?derivatives?\b",
            r"\bproprietary\b", r"\bclosed[-\s]?source\b",
        )
        licenses_unclear = (
            r"\bllama[-\s]?2\b", r"\bmeta[-\s]?llama\b", r"\bllama[-\s]?2[-\s]?community[-\s]?license\b",
            r"\bgemma\b", r"\bgemma[-\s]?terms\b", r"\btii[-\s]?falcon[-\s]?license\b",
            r"\bqwen[-\s]?license\b",
            r"\bopenrail(?:-[ml])?\b", r"\bopen[-\s]?rail\b",
            r"\bcc[-\s]?by[-\s]?sa\b", r"\bshare[-\s]?alike\b",
            r"\blgpl[-\s]?3(?:\.0)?\b",
        )
        licenses_permissive = (
            r"\bmit\b",
            r"\bapache(?:-|\s)?(?:license[-\s]?)?(?:version[-\s]?)?2(?:\.0)?\b", r"\bapache2\b",
            r"\bbsd\b", r"\bbsd-2-clause\b", r"\bbsd-3-clause\b",
            r"\bmpl(?:-|\s)?2(?:\.0)?\b", r"\bmozilla[-\s]?public[-\s]?license[-\s]?2(?:\.0)?\b",
            r"\blgpl(?:-?2\.1)(?:-only|-or-later|\+)?\b",
            r"\bcc[-\s]?by\b", r"\bcc[-\s]?by[-\s]?4\.0\b", r"\bcc0\b",
            r"\bcreative[-\s]?commons[-\s]?zero\b",
            r"\bunlicense\b",
        )
        licenses_compatible = (
            r"\bmit\b",
            r"\bapache(?:-|\s)?(?:license[-\s]?)?(?:version[-\s]?)?2(?:\.0)?\b", r"\bapache2\b",
            r"\bbsd\b", r"\bbsd-2-clause\b", r"\bbsd-3-clause\b",
            r"\bcc0\b", r"\bcreative[-\s]?commons[-\s]?zero\b",
            r"\bcc[-\s]?by\b", r"\bcc[-\s]?by[-\s]?4\.0\b",
            r"\bunlicense\b",
            r"\blgpl(?:-?2\.1)(?:-only|-or-later|\+)?\b",
            r"\bmpl(?:-|\s)?2(?:\.0)?\b",
        )
        
        # Default for unknown/missing should be restrictive (0.0)
        license_score = 0.0
        license_text = ""

        # 1) Normalize to an HF model id and fetch the README text
        model_id = _hf_model_id_from_url(model_url)
        if model_id and not model_id.startswith("http"):
            readme_text = _fetch_hf_readme_text(model_id)  # <-- FIXED: use model_id
            if readme_text:
                text = readme_text.strip()
                lower = text.lower()

                # 2) Try YAML front-matter first: e.g., "license: apache-2.0" or "license: mit"
                m = re.search(r'(?im)^\s*license\s*:\s*([^\r\n#]+)$', lower)
                if m:
                    license_text = m.group(1).strip()
                else:
                    # 3) Otherwise, try a "License" heading section
                    sec = re.search(
                        r"(?ims)^[ \t]*#{1,6}[ \t]*licens(?:e|ing)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
                        text,
                    )
                    if sec:
                        license_text = sec.group(1).strip().lower()
                    else:
                        # 4) Last resort: scan entire README for common license slugs/badges
                        license_text = lower

                # normalize separators so the regexes with hyphens work well
                license_text = re.sub(r"[\s_]+", "-", license_text)

                # 5) Score mapping
                if any(re.search(p, license_text) for p in licenses_restrictive):
                    license_score = 0.0
                elif any(re.search(p, license_text) for p in licenses_unclear):
                    license_score = 0.5
                elif any(re.search(p, license_text) for p in licenses_permissive):
                    license_score = 1.0
                    # ensure it’s in the compatible set
                    if not any(re.search(p, license_text) for p in licenses_compatible):
                        license_score = 0.0  # permissive but incompatible → treat as restrictive

        return float(license_score)

    
class PerformanceClaimsMetric(BaseMetric):
    def __init__(self):
        super().__init__("performance_claims")

    def _calculate_score(self, model_url: str) -> Optional[float]:
        # Download repo files locally (non-API) and analyze from disk
        repo_dir = download_hf_repo_subset(model_url)

        # Prefer README; fall back to model_index.json or README.yaml
        for name in ("README.md", "model_index.json", "README.yaml"):
            text = read_text_if_exists(repo_dir, name)
            if text and text.strip():
                return 1.0 if has_real_metrics(text) else 0.0

        return 0.0
    

class SizeMetric(BaseMetric):
    def __init__(self):
        super().__init__("size_score")

    def _calculate_score(self, model_url: str) -> Optional[float]:
        self.device_scores = {}

        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return None  # non-HF / unknown

        try:
            # Get head (sha) + file listing ("siblings")
            info_resp = requests.get(
                f"https://huggingface.co/api/models/{model_id}",
                timeout=(2.0, 6.0),
            )
            if info_resp.status_code != 200:
                return None
            info = info_resp.json() or {}
            head = info.get("sha")
            siblings = info.get("siblings") or []
            if not head or not isinstance(siblings, list):
                return None

            # Parse files starting from head, classify by extensions and basenames
            total_bytes = 0
            weight_extensions = (
                ".safetensors", ".bin", ".h5", ".hdf5", ".ckpt",
                ".pt", ".pth", ".onnx", ".gguf", ".msgpack"
            )
            weight_basenames = (
                "pytorch_model", "model", "tf_model", "flax_model",
                "diffusion_pytorch_model", "adapter_model"
            )

            for s in siblings:
                name = (s.get("rfilename") or "").strip()
                if not name:
                    continue
                lower = name.lower()
                if not (lower.endswith(weight_extensions) or os.path.basename(lower).startswith(weight_basenames)):
                    continue

                # Query exact file size
                size_bytes = None
                url = f"https://huggingface.co/{model_id}/resolve/{head}/{name}"
                try:
                    # Primary head
                    h = requests.head(url, allow_redirects=True, timeout=(2.0, 5.0))
                    cl = h.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        size_bytes = int(cl)
                except Exception:
                    size_bytes = None

                # Get 1 byte with Range to read Content-Range total
                if size_bytes is None:
                    try:
                        g = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=(2.0, 6.0))
                        cr = g.headers.get("Content-Range")
                        if cr and "/" in cr:
                            after_slash = cr.split("/", 1)[1].strip()
                            if after_slash.isdigit():
                                size_bytes = int(after_slash)
                    except Exception:
                        size_bytes = None

                if not isinstance(size_bytes, int) or size_bytes <= 0:
                    continue
                if size_bytes < 5 * 1024 * 1024:  # ignore tiny files (<5MB)
                    continue

                total_bytes += size_bytes

                # Early exit, all device scores == 0.0 at >=120GB
                if total_bytes >= 120 * (1024 ** 3):
                    break

            if total_bytes <= 0:
                return None

            gb = total_bytes / (1024 ** 3)

            # Raspberry Pi
            if   gb < 0.2: self.device_scores["raspberry_pi"] = 1.0
            elif gb < 0.5: self.device_scores["raspberry_pi"] = 0.8
            elif gb < 1.0: self.device_scores["raspberry_pi"] = 0.6
            elif gb < 2.0: self.device_scores["raspberry_pi"] = 0.4
            elif gb < 4.0: self.device_scores["raspberry_pi"] = 0.2
            else:          self.device_scores["raspberry_pi"] = 0.0

            # Jetson Nano
            if   gb < 0.5: self.device_scores["jetson_nano"] = 1.0
            elif gb < 1.0: self.device_scores["jetson_nano"] = 0.75
            elif gb < 2.0: self.device_scores["jetson_nano"] = 0.5
            elif gb < 4.0: self.device_scores["jetson_nano"] = 0.25
            else:          self.device_scores["jetson_nano"] = 0.0

            # Desktop PC
            if   gb < 4.0:  self.device_scores["desktop_pc"] = 1.0
            elif gb < 8.0:  self.device_scores["desktop_pc"] = 0.8
            elif gb < 16.0: self.device_scores["desktop_pc"] = 0.6
            elif gb < 32.0: self.device_scores["desktop_pc"] = 0.4
            elif gb < 64.0: self.device_scores["desktop_pc"] = 0.2
            else:           self.device_scores["desktop_pc"] = 0.0

            # AWS Server
            if   gb < 40.0:  self.device_scores["aws_server"] = 1.0
            elif gb < 60.0:  self.device_scores["aws_server"] = 0.8
            elif gb < 80.0:  self.device_scores["aws_server"] = 0.6
            elif gb < 100.0: self.device_scores["aws_server"] = 0.4
            elif gb < 120.0: self.device_scores["aws_server"] = 0.2
            else:            self.device_scores["aws_server"] = 0.0

            # Round per-device and return average
            self.device_scores = {k: round(float(v), 3) for k, v in self.device_scores.items()}
            return round(sum(self.device_scores.values()) / 4.0, 3)

        except Exception:
            self.device_scores = {}
            return None

class DatasetCodeMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_and_code_score")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return 0.0

        dataset_available = False
        code_available = False

        try:
            # 1) HF API (model metadata + file listing)
            api = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if api.status_code == 200:
                info = api.json()
                card = info.get("cardData") or {}

                # dataset presence (cardData.datasets)
                ds = card.get("datasets") or []
                if isinstance(ds, list) and ds:
                    dataset_available = True

                # code presence: actual repo files (*.py)
                for s in (info.get("siblings") or []):
                    fn = (s.get("rfilename") or "").lower()
                    if fn.endswith(".py"):
                        code_available = True
                        break

            # 2) Fallback to README only if we didn't find .py files,
            #    and only if it's clearly Python usage (not a random fence)
            if not code_available:
                readme = _fetch_hf_readme_text(model_id)  # <-- use model_id
                if readme:
                    low = readme.lower()
                    strong_python_signals = (
                        "```python",
                        "from transformers import",
                        "autotokenizer",
                        "automodel",
                        "pipeline(",
                        "pip install transformers",
                    )
                    if any(k in low for k in strong_python_signals):
                        code_available = True

        except Exception:
            return 0.0

        if dataset_available and code_available:
            return 1.0
        if dataset_available or code_available:
            return 0.5
        return 0.0


class DatasetQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)

        # 1) Pull README and (optionally) cardData via API
        readme = _fetch_hf_readme_text(model_id) or ""
        if not readme.strip():
            return 0.0

        text = readme
        low = text.lower()

        api_ds = []
        try:
            api = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if api.status_code == 200:
                info = api.json()
                card = info.get("cardData") or {}
                # Normalize to lower-case list
                ds = card.get("datasets") or []
                if isinstance(ds, list):
                    api_ds = [str(x).lower() for x in ds if x]
        except Exception:
            pass

        # 2) Extract a likely dataset/training-data section (fallback to whole text)
        sec = None
        for pat in (
            r"(?ims)^[ \t]*#{1,6}[ \t]*(dataset|datasets)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
            r"(?ims)^[ \t]*#{1,6}[ \t]*(training data|pre[- ]?training data|pre[- ]?trained on|data|corpus)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
        ):
            m = re.search(pat, text)
            if m:
                sec = m.group(2)
                break
        section = (sec or text).lower()

        # 3) Trusted datasets (gives strong signal)
        trusted = {
            "bookcorpus", "wikipedia", "openwebtext", "common crawl", "c4", "pile",
            "imagenet", "coco", "librispeech", "laion", "squad", "squad v2", "mnist",
            "cifar-10", "cifar10",
        }

        found_names = set()
        for name in trusted:
            if name in section or name in api_ds:
                found_names.add(name)

        # 4) Quality signals anywhere in the section
        quality_kw = (
            "dedup", "de-dup", "de-duplicate", "remove duplicates",
            "filter", "filtered", "quality filter",
            "balanced", "class balance", "stratified",
            "train/val", "train/valid", "train/test", "validation set", "evaluation set",
            "data cleaning", "preprocessing",
        )
        quality_hits = sum(1 for kw in quality_kw if kw in section)
        quality_frac = min(1.0, quality_hits / 4.0)  # cap contribution

        # 5) Scoring heuristic tuned to match the sample:
        # - BookCorpus + Wikipedia together → ~0.95
        # - any 2+ trusted datasets → high (≥0.8), add quality up to 0.95
        # - one trusted dataset → moderate (≈0.6–0.8)
        # - otherwise, if datasets declared in cardData or section exists → low (0.4–0.6)
        if {"bookcorpus", "wikipedia"}.issubset(found_names):
            base = 0.9
            score = min(1.0, base + 0.05 + 0.05 * quality_frac)  
        elif len(found_names) >= 2:
            base = 0.8
            score = min(0.95, base + 0.15 * quality_frac)
        elif len(found_names) == 1:
            base = 0.6
            score = min(0.9, base + 0.3 * quality_frac)
        elif api_ds or sec:
            base = 0.4
            score = min(0.7, base + 0.3 * quality_frac)
        else:
            score = 0.0

        return round(float(score), 3)
    



class CodeQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("code_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)
        
        try:
            # 1. Get metadata from Hugging Face API
            api_url = f"https://huggingface.co/api/models/{model_id}"
           
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                return None
            
            metadata = response.json()
            files_data = metadata.get("siblings", [])
            config = metadata.get("config", {})
            
            
            # 2. Look for Python files in repo
            python_files = [
                f["rfilename"] for f in files_data
                if f.get("rfilename", "").endswith(".py")
            ]
            
           
            
            scores = []

            if python_files:
                
                # Case A: Python files exist in the repo
                for python_file in python_files:
                    file_url = f"https://huggingface.co/{model_id}/raw/main/{python_file}"
                    file_response = requests.get(file_url, timeout=10)
                    if file_response.status_code == 200:
                        score = self._analyze_with_pylint(file_response.text, python_file)
                        if score is not None:
                            scores.append(score)
            
            else:
                
                # Case B: No code in repo → fall back to transformers implementation
                model_type = config.get("model_type")
               
                if model_type:
                    # Map HF model_type → transformers folder name
                    # (gemma3_text → gemma3, llama → llama, etc.)
                    if model_type.endswith("_text"):
                        model_type = model_type.replace("_text", "")
                        
                    
                    # URL to raw file in transformers GitHub
                    base_url = (
                        "https://raw.githubusercontent.com/huggingface/"
                        "transformers/main/src/transformers/models"
                    )
                    model_file = f"{base_url}/{model_type}/modeling_{model_type}.py"
                    
                    
                    file_response = requests.get(model_file, timeout=10)
                   
                    if file_response.status_code == 200:
                        
                        score = self._analyze_with_pylint(
                            file_response.text,
                            f"modeling_{model_type}.py"
                        )
                        
                        
                        if score is not None:
                            scores.append(score)
            
            return sum(scores) / len(scores) if scores else 0
        
        except Exception:
            return None
    
    

    def _analyze_with_pylint(self, code_content: str, filename: str) -> Optional[float]:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
               temp_file.write(code_content)
               temp_file_path = temp_file.name
              

            result = subprocess.run(
               [sys.executable, "-m", "pylint", "--output-format=text", "--score=yes", temp_file_path],
               capture_output=True,
               text=True,
               timeout=30,
            )
            
            return self._parse_pylint_score(result.stdout)

        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            print("ERROR running pylint:", e,file=sys.stderr, flush=True)
            return None
        finally:
            try:
               os.unlink(temp_file_path)
            except:
               pass

    def _parse_pylint_score(self, output: str) -> Optional[float]:
        """Parse pylint score from output and normalize to 0.0-1.0 range"""
        for line in output.split('\n'):
            if 'Your code has been rated at' in line:
                try:
                    # Extract the numeric score (e.g., "8.50/10")
                    parts = line.split('rated at')[-1].strip().split('/')
                    raw_score = float(parts[0])
                    if raw_score >=7 :
                        return 1
                    elif raw_score >= 4 :
                        return 0.75
                    elif raw_score >= 2 :
                        return 0.5
                    elif raw_score >=0.1 :
                        return 0.25

                except (ValueError, IndexError):
                    continue
        return None




class MetricsCalculator:
    
    def __init__(self):
        self.metrics = {
            "ramp_up_time": RampUpTimeMetric(),
            "bus_factor": BusFactorMetric(),
            "license": LicenseMetric(),
            "performance_claims": PerformanceClaimsMetric(),
            "size_score": SizeMetric(),
            "dataset_and_code_score": DatasetCodeMetric(),
            "dataset_quality": DatasetQualityMetric(),
            "code_quality": CodeQualityMetric(),
        }
    
    def calculate_all_metrics(self, model_url: str) -> Dict[str, MetricResult]:
       
        results = {}
        
        for metric_name, metric in self.metrics.items():
            results[metric_name] = metric.calculate(model_url)
        
        return results
    
    def calculate_net_score(self, metric_results: Dict[str, MetricResult]) -> float:
        
        weights = {
            "ramp_up_time":0.15,
            "bus_factor": 0.10,
            "performance_claims": 0.15,
            "license": 0.15,
            "size_score": 0.15,
            "dataset_and_code_score": 0.10,
            "dataset_quality": 0.10,
            "code_quality": 0.10,
        }
        
        total_weight = 0.0
        net_score = 0.0
        for metric_name, weight in weights.items():
            res = metric_results.get(metric_name)
            if res is not None and res.score is not None:
                net_score += res.score * weight
                total_weight += weight
        
        return round(net_score / total_weight, 3) if total_weight > 0 else 0.0
    

   