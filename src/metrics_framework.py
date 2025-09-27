
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from .scoring import _hf_model_id_from_url
from datetime import datetime
import time
import re
import requests
import math
import tempfile
import subprocess
import os

#==========HELPER for Performance Metric=============================
PERF_KEYWORDS = [
    "accuracy","f1","precision","recall","auc","bleu","rouge",
    "mse","rmse","mae","perplexity","wer","cer","map",
    "results","benchmark","evaluation","eval","score"
]

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
    score: Optional[float]  # optional to allow for None if calculation failed
    latency_ms: int

class BaseMetric(ABC):
    """Abstract base class for all metrics"""
    
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
        if "/" not in model_id or model_id.startswith("http"):
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
        if "/" not in model_id or model_id.startswith("http"):
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
          0.0 = restrictive or incompatible (e.g., GPL/AGPL, Non-Commercial, No-Derivatives, Proprietary)
        """
        # Hardcoded regexes for common licenses, grouped by permissiveness
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

        # Hardcoded regexes for known LGPL-2.1 compatible licenses
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
        
        license_score = 0.5 # default (unclear)
        license_text = ""
        # Extract "License" text from README
        model_id = _hf_model_id_from_url(model_url)
        if "/" in model_id and not model_id.startswith("http"):
            readme_text = _fetch_hf_readme_text(model_url)
            if readme_text:
                match = re.search(
                    r"(?im)^[ \t]*#{1,6}[ \t]*licens(?:e|ing)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
                    readme_text,
                    flags=re.DOTALL,
                )
                if match:
                    license_text = match.group(1).strip().lower()

            if license_text:
                license_text = re.sub(r"[\s_]+", "-", license_text)

                # Assigning score based on license type
                if any(re.search(pattern, license_text) for pattern in licenses_restrictive):
                    license_score = 0.0 # restrictive
                elif any(re.search(pattern, license_text) for pattern in licenses_unclear):
                    license_score = 0.5 # unclear
                elif any(re.search(pattern, license_text) for pattern in licenses_permissive):
                    license_score = 1.0 # permissive

                # Double-check for LGPL-2.1 compatibility (only if score == 1.0)
                if license_score == 1.0 and not any(re.search(p, license_text) for p in licenses_compatible):
                    license_score = 0.0 # permissive but incompatible, downgrade to 0.0

        return license_score
    
class PerformanceClaimsMetric(BaseMetric):
    def __init__(self):
        super().__init__("performance_claims")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        text = _fetch_hf_readme_text(model_url)
        if not text.strip():
            return 0.0  # no README → no claims
        for kw in PERF_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE):
                return 1.0
        return 0.0

class SizeMetric(BaseMetric):
    def __init__(self):
        super().__init__("size_score")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)
        if "/" not in model_id or model_id.startswith("http"):
            return None  # unknown size
        
        try:
            r = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=10)
            if r.status_code != 200:
                return None  # unknown size
            data = r.json()
            siblings = data.get("siblings") or []

            #match pytorch weight names
            pat_bin  = re.compile(r"^pytorch_model(?:-\d{5}-of-\d{5})?\.bin$", re.IGNORECASE)
            pat_st   = re.compile(r"^model(?:-\d{5}-of-\d{5})?\.safetensors$", re.IGNORECASE)
            pat_st2  = re.compile(r"^pytorch_model(?:-\d{5}-of-\d{5})?\.safetensors$", re.IGNORECASE)  # rare but seen

            total_bytes = 0
            for s in siblings:
                name = (s.get("rfilename") or "").strip()
                sz = s.get("size")
                if not isinstance(sz, int):
                    continue
                if pat_bin.match(name) or pat_st.match(name) or pat_st2.match(name):
                    total_bytes += sz
            
            if total_bytes <= 0:
                return None  # unknown size
            
            gb = total_bytes / (1024**3)  # bytes to GB

            if gb < 1: return 1.0
            if gb < 10: return 0.75
            if gb < 20: return 0.5
            if gb < 40: return 0.25
            return 0.0
        except Exception:
            return None  # unknown size
        
class DatasetCodeMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_and_code_score")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)
        # Only apply to valid Hugging Face model identifiers.
        if "/" not in model_id or model_id.startswith("http"):
            return 0.0

        dataset_available = False
        code_available = False

        try:
            # Fetch the model's metadata from the HF API
            api_resp = requests.get(
                f"https://huggingface.co/api/models/{model_id}", timeout=10
            )
            if api_resp.status_code == 200:
                info = api_resp.json()
                card = info.get("cardData") or {}
                # Check for datasets field in the card
                datasets = card.get("datasets") or []
                if isinstance(datasets, list) and len(datasets) > 0:
                    dataset_available = True

                # Inspect repository file listing for Python files
                siblings = info.get("siblings") or []
                for s in siblings:
                    filename = (s.get("rfilename") or "").lower()
                    if filename.endswith(".py"):
                        code_available = True
                        break

            # If we didn't find Python files, look for code snippets in the README
            if not code_available:
                readme_text = _fetch_hf_readme_text(model_url)
                if readme_text:
                    # A fenced code block (```some code```) implies code availability
                    if "```" in readme_text:
                        code_available = True
                    else:
                        lowered = readme_text.lower()
                        # Keywords commonly used in sections containing example code
                        for kw in [
                            "example",
                            "usage",
                            "import",
                            "code snippet",
                            "how to use",
                        ]:
                            if kw in lowered:
                                code_available = True
                                break
        except Exception:
            # On error, fail conservatively
            return 0.0

        # Determine final score per rules
        if dataset_available and code_available:
            return 1.0
        if dataset_available or code_available:
            return 0.5
        return 0.0

class DatasetQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        readme = _fetch_hf_readme_text(model_url)
        if not readme.strip():
            return 0.0

        # Try to extract a dataset section from the README
        ds_match = re.search(
            r"(?im)^[ \t]*#{1,6}[ \t]*dataset(s)?[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
            readme,
            flags=re.DOTALL,
        )
        if not ds_match:
            return 0.0  # no dataset section found

        dataset_section = ds_match.group(2).lower()

        # Define keywords for each dimension
        integrity_keywords = [
            "integrity",
            "trustworthy",
            "clean",
            "quality",
            "verified",
            "uncorrupted",
            "honest",
        ]
        completeness_keywords = [
            "complete",
            "full",
            "coverage",
            "no missing",
            "all records",
            "complete dataset",
        ]
        consistency_keywords = [
            "consistent",
            "uniform",
            "normalized",
            "standardized",
            "same across",
        ]

        # Check for keyword presence
        integrity_score = any(k in dataset_section for k in integrity_keywords)
        completeness_score = any(k in dataset_section for k in completeness_keywords)
        consistency_score = any(k in dataset_section for k in consistency_keywords)

        # Compute a normalized score: average of the three factors
        total = int(integrity_score) + int(completeness_score) + int(consistency_score)
        if total == 0:
            return 0.0
        return round(total / 3.0, 3)
    



class CodeQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("code_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)
     
        try:
            # Get list of files from Hugging Face API
            api_url = f"https://huggingface.co/api/models/{model_id}"
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                return None
            
            files_data = response.json().get('siblings', [])
           
            
            # Filter for Python files
            python_files = []
            for file_info in files_data:
                filename = file_info.get('rfilename', '')
                if filename and filename.endswith('.py'):
                    python_files.append(filename)
            
            if not python_files:
                return 0.5  # No Python files found
            
            # Analyze each Python file
            scores = []
            for python_file in python_files:
                file_url = f"https://huggingface.co/{model_id}/raw/main/{python_file}"
                file_response = requests.get(file_url, timeout=10)
                if file_response.status_code == 200:
                    score = self._analyze_with_pylint(file_response.text, python_file)
                    if score is not None:
                        scores.append(score)
            
            return sum(scores) / len(scores) if scores else 0.5
            
        except Exception:
            return None
    
    def _analyze_with_pylint(self, code_content: str, filename: str) -> Optional[float]:
        """
        Analyze a single Python file's content using pylint
        Returns normalized score (0.0 to 1.0) or None if analysis fails
        """
        # Create a temporary file with the code content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(code_content)
            temp_file_path = temp_file.name
        
        try:
            # Run pylint on the temporary file
            result = subprocess.run(
                ['pylint', '--output-format=text', '--score=yes', temp_file_path],
                capture_output=True,
                text=True,
                timeout=30  # shorter timeout for single files
            )
            
            # Parse the pylint score from output
            return self._parse_pylint_score(result.stdout)
            
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None
        finally:
            # Clean up temporary file
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
                    return max(0.0, min(1.0, raw_score / 10.0))
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