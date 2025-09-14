
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
import time

@dataclass
class MetricResult:
    score: float  
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
            latency_ms = (time.time_ns() - start_time) 
            return MetricResult(score, latency_ms)
        except Exception as e:
            return MetricResult(0.0, (time.time_ns() - start_time) // 1_000_000)
    
    @abstractmethod
    def _calculate_score(self, model_url: str) -> float:
        
        pass


class RampUpTimeMetric(BaseMetric):
    def __init__(self):
        super().__init__("ramp_up_time")
    
    def _calculate_score(self, model_url: str) -> float:
        
        return 1

class BusFactorMetric(BaseMetric):
    def __init__(self):
        super().__init__("bus_factor")
    
    def _calculate_score(self, model_url: str) -> float:
        
        return 1

class LicenseMetric(BaseMetric):
    def __init__(self):
        super().__init__("license")
    
    def _calculate_score(self, model_url: str) -> float:
        
        return 1  
class PerformanceClaimsMetric(BaseMetric):
    def __init__(self):
        super().__init__("performance_claims")
    
    def _calculate_score(self, model_url: str) -> float:
        
        return 1

class SizeMetric(BaseMetric):
    def __init__(self):
        super().__init__("size_score")
    
    def _calculate_score(self, model_url: str) -> float:
       
        return 1
   

class DatasetCodeMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_and_code_score")
    
    def _calculate_score(self, model_url: str) -> float:
       
        return 1

class DatasetQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("dataset_quality")
    
    def _calculate_score(self, model_url: str) -> float:
       
        return 1
class CodeQualityMetric(BaseMetric):
    def __init__(self):
        super().__init__("code_quality")
    
    def _calculate_score(self, model_url: str) -> float:
      
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
            "ramp_up_time":0.1,
            "bus_factor": 0.1,
            "performance_claims": 0.1,
            "license": 0.1,
            "size_score": 0.1,
            "dataset_and_code_score": 0.1,
            "dataset_quality": 0.1,
            "code_quality": 0.1,
        }
        
        net_score = 0.0
        for metric_name, weight in weights.items():
            if metric_name in metric_results:
                net_score += metric_results[metric_name].score * weight
        
        return max(0.0, min(1.0, net_score))


