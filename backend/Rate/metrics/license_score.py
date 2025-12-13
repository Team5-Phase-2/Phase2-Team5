
"""backend.Rate.metrics.license_score

Heuristic license classifier that assigns a permissiveness score based on
license text found in the repository README or license sections.

Returns a float in [0.0, 1.0] where 1.0 indicates permissive licensing and
0.0 indicates restrictive or proprietary licensing. `None` is returned on
error with latency included as the second tuple item.
"""

from typing import Optional, Tuple
import time, re
from .utils import fetch_hf_readme_text
from scoring import _hf_model_id_from_url

def license_score(model_url: str, code_url: str, dataset_url: str) -> Tuple[Optional[float], int]:
    start_ns = time.time_ns()
    try:
        licenses_restrictive = (
            r"\bagpl(?:-?3(?:\.0)?)?(?:-only|-or-later|\+)?\b",
            r"\bgpl(?:-?2(?:\.0)?|-?3(?:\.0)?)(?:-only|-or-later|\+)?\b",
            r"\bgplv2\b", r"\bgplv3\b",
            r"\bcc-?by-?nc\b", r"\bcc-?nc\b", r"\bnon[-\s]?commercial\b", r"\bnoncommercial\b",
            r"\bresearch[-\s]?only\b", r"\bresearch[-\s]?use\b",
            r"\bno[-\s]?derivatives?\b",
            r"\bproprietary\b", r"\bclosed[-\s]?source\b",)

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

        license_score_val = 0.0
        license_text = ""

        model_id = _hf_model_id_from_url(model_url)
        if model_id and not model_id.startswith("http"):
            readme_text = fetch_hf_readme_text(model_id)
            if readme_text:
                text = readme_text.strip()
                lower = text.lower()

                m = re.search(r'(?im)^\s*license\s*:\s*([^\r\n#]+)$', lower)
                if m:
                    license_text = m.group(1).strip()
                else:
                    sec = re.search(
                        r"(?ims)^[ \t]*#{1,6}[ \t]*licens(?:e|ing)\b[^\n]*\n(.*?)(?=^[ \t]*#{1,6}[ \t]+\S|\Z)",
                        text,
                    )
                    if sec:
                        license_text = sec.group(1).strip().lower()
                    else:
                        license_text = lower

                license_text = re.sub(r"[\s_]+", "-", license_text)

                if any(re.search(p, license_text) for p in licenses_restrictive):
                    license_score_val = 0.0
                elif any(re.search(p, license_text) for p in licenses_unclear):
                    license_score_val = 0.5
                elif any(re.search(p, license_text) for p in licenses_permissive):
                    license_score_val = 1.0
                    if not any(re.search(p, license_text) for p in licenses_compatible):
                        license_score_val = 0.0

        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return float(license_score_val), latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_ns) // 1_000_000
        return None, latency_ms
