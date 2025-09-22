
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from scoring import _hf_model_id_from_url
import time
import re
import requests
import math

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
        
        return 1

class LicenseMetric(BaseMetric):
    def __init__(self):
        super().__init__("license")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
        model_id = _hf_model_id_from_url(model_url)

        if "/" not in model_id or model_id.startswith("http"):
            return 0.5 # unclear license
        
        # fetch readme
        readme_url = f"https://huggingface.co/{model_id}/raw/main/README.md"
        try:
            resp = requests.get(readme_url, timeout=10)
            if resp.status_code != 200 or not resp.text:
                return 0.5 # unclear license -> 0.5
            md = resp.text
        except Exception:
            return 0.5 # unclear license -> 0.5
        
        m = re.search(
            r"(?im)^[ \t]*#{1,6}[ \t]*license\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
            md,
            flags=re.DOTALL,
        )
        if not m:
            return 0.5  # no explicit License section (unclear) -> 0.5
        
        section = m.group(1).lower()

        # Compatible: explicitly mentions "lgpl" AND "2.1" in the License section
        if ("lgpl" in section) and re.search(r"\b2\.1\b", section):
            return 1.0
        
        # Incompatible: mentions AGPL/GPL (without the 'L'), or proprietary / non-commercial / no license
        if ("lgpl" not in section) and re.search(r"\b(?:agpl|gpl)\b", section):
            return 0.0
        if re.search(r"\bproprietary\b|\bnon[- ]?commercial\b|\bno license\b", section):
            return 0.0
        
        return 0.5  # unclear license -> 0.5
    
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
       
        return 1

class DatasetQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
       
        return 1
    
import tempfile
import subprocess
import os
from typing import Optional

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
    
# Quick test
metric = CodeQualityMetric()

# Test with a known model
test_url ="https://huggingface.co/facebook/bart-large"

print(f"Testing: {test_url}")

result = metric.calculate(test_url)
print(f"Score: {result.score}")
print(f"Latency: {result.latency_ms}ms") 