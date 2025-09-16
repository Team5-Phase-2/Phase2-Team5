
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from src.scoring import _hf_model_id_from_url
import time
import re
import requests

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
        
        return 1

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
        
        return 1

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
    
class CodeQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("code_quality")
    
    def _calculate_score(self, model_url: str) -> Optional[float]:
      
        return 1

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