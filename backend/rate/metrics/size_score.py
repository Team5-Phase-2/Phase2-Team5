# metrics/size_score.py
from typing import Optional, Tuple
import time, requests, os, math
from scoring import _hf_model_id_from_url

def size_score(model_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        device_scores = {}
        model_id = _hf_model_id_from_url(model_url)
        if model_id.startswith("http"):
            return None, (time.time_ns() - start_ns) // 1_000_000

        info_resp = requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=(2.0, 6.0))
        if info_resp.status_code != 200:
            return None, (time.time_ns() - start_ns) // 1_000_000
        info = info_resp.json() or {}
        head = info.get("sha")
        siblings = info.get("siblings") or []
        if not head or not isinstance(siblings, list):
            return None, (time.time_ns() - start_ns) // 1_000_000

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

            size_bytes = None
            url = f"https://huggingface.co/{model_id}/resolve/{head}/{name}"
            try:
                h = requests.head(url, allow_redirects=True, timeout=(2.0, 5.0))
                cl = h.headers.get("Content-Length")
                if cl and cl.isdigit():
                    size_bytes = int(cl)
            except Exception:
                size_bytes = None

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
            if size_bytes < 5 * 1024 * 1024:
                continue

            total_bytes += size_bytes
            if total_bytes >= 120 * (1024 ** 3):
                break

        if total_bytes <= 0:
            return None, (time.time_ns() - start_ns) // 1_000_000

        gb = total_bytes / (1024 ** 3)

        # Raspberry Pi
        if   gb < 0.2: device_scores["raspberry_pi"] = 1.0
        elif gb < 0.5: device_scores["raspberry_pi"] = 0.8
        elif gb < 1.0: device_scores["raspberry_pi"] = 0.6
        elif gb < 2.0: device_scores["raspberry_pi"] = 0.4
        elif gb < 4.0: device_scores["raspberry_pi"] = 0.2
        else:          device_scores["raspberry_pi"] = 0.0

        # Jetson Nano
        if   gb < 0.5: device_scores["jetson_nano"] = 1.0
        elif gb < 1.0: device_scores["jetson_nano"] = 0.75
        elif gb < 2.0: device_scores["jetson_nano"] = 0.5
        elif gb < 4.0: device_scores["jetson_nano"] = 0.25
        else:          device_scores["jetson_nano"] = 0.0

        # Desktop PC
        if   gb < 4.0:  device_scores["desktop_pc"] = 1.0
        elif gb < 8.0:  device_scores["desktop_pc"] = 0.8
        elif gb < 16.0: device_scores["desktop_pc"] = 0.6
        elif gb < 32.0: device_scores["desktop_pc"] = 0.4
        elif gb < 64.0: device_scores["desktop_pc"] = 0.2
        else:           device_scores["desktop_pc"] = 0.0

        # AWS Server
        if   gb < 40.0:  device_scores["aws_server"] = 1.0
        elif gb < 60.0:  device_scores["aws_server"] = 0.8
        elif gb < 80.0:  device_scores["aws_server"] = 0.6
        elif gb < 100.0: device_scores["aws_server"] = 0.4
        elif gb < 120.0: device_scores["aws_server"] = 0.2
        else:            device_scores["aws_server"] = 0.0

        device_scores = {k: round(float(v), 3) for k, v in device_scores.items()}
        score = round(sum(device_scores.values()) / 4.0, 3)
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
