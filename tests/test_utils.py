"""
Unit tests for backend.Rate.metrics.utils

Covers:
- fetch_hf_readme_text
- query_genai
- analyze_code
"""

import pytest
import backend.Rate.metrics.utils as ut


class MockGetResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class MockPostResp:
    def __init__(self, json_data=None):
        self._json_data = json_data or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


def test_fetch_hf_readme_text_success(monkeypatch):
    monkeypatch.setattr(ut, "_hf_model_id_from_url", lambda _: "owner/repo")

    def fake_get(url, timeout=10):
        assert url == "https://huggingface.co/owner/repo/raw/main/README.md"
        return MockGetResp(status_code=200, text="README CONTENT")

    monkeypatch.setattr(ut.requests, "get", fake_get)

    assert ut.fetch_hf_readme_text("https://huggingface.co/owner/repo") == "README CONTENT"


def test_fetch_hf_readme_text_non_200_returns_empty(monkeypatch):
    monkeypatch.setattr(ut, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(ut.requests, "get", lambda *a, **k: MockGetResp(status_code=404, text="nope"))

    assert ut.fetch_hf_readme_text("x") == ""


def test_fetch_hf_readme_text_malformed_model_id_returns_empty(monkeypatch):
    # split("/") will fail -> should be caught and return ""
    monkeypatch.setattr(ut, "_hf_model_id_from_url", lambda _: "not_a_pair")

    assert ut.fetch_hf_readme_text("x") == ""


def test_fetch_hf_readme_text_request_exception_returns_empty(monkeypatch):
    monkeypatch.setattr(ut, "_hf_model_id_from_url", lambda _: "owner/repo")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(ut.requests, "get", boom)

    assert ut.fetch_hf_readme_text("x") == ""


def test_query_genai_success(monkeypatch):
    monkeypatch.setenv("PURDUE_GENAI_API_KEY", "abc123")

    def fake_post(url, headers=None, json=None, timeout=60):
        assert url == "https://genai.rcac.purdue.edu/api/chat/completions"
        assert headers["Authorization"] == "Bearer abc123"
        assert headers["Content-Type"] == "application/json"
        assert json["model"] == "llama3.3:70b"
        assert json["messages"][0]["role"] == "user"
        assert json["messages"][0]["content"] == "hello"
        assert json["stream"] is False
        return MockPostResp(json_data={"ok": True})

    monkeypatch.setattr(ut.requests, "post", fake_post)

    resp = ut.query_genai("hello")
    assert resp["statusCode"] == 200
    assert '"ok": true' in resp["body"].lower()


def test_query_genai_request_exception_returns_tuple(monkeypatch):
    monkeypatch.setenv("PURDUE_GENAI_API_KEY", "abc123")

    def fake_post(*a, **k):
        raise ut.requests.exceptions.RequestException("bad request")

    monkeypatch.setattr(ut.requests, "post", fake_post)

    out = ut.query_genai("hello")
    # On failure, utils.query_genai returns (exception, api_key)
    assert isinstance(out, tuple)
    assert "bad request" in str(out[0]).lower()
    assert out[1] == "abc123"


def test_analyze_code_syntax_error_returns_zero():
    assert ut.analyze_code("def broken(:\n  pass") == 0.0


def test_analyze_code_clean_code_scores_high():
    code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

x = add(1, 2)
'''
    score = ut.analyze_code(code)
    assert 0.8 <= score <= 1.0


def test_analyze_code_penalties_reduce_score():
    # Hits: missing docstring, long function (>50 body stmts), risky eval,
    # global usage, unused import, long line >120
    long_body = "\n".join(["    x = 1"] * 55)
    code = (
        "import os\n"            # unused import
        "g1 = 0\n"
        "global_var = 1\n"
        "def f():\n"             # missing docstring
        "    global global_var\n"
        f"{long_body}\n"
        "    eval('1+1')\n"      # risky call
        + ("a = '" + ("x" * 130) + "'\n")  # long line >120
    )

    score = ut.analyze_code(code)
    assert 0.0 <= score < 0.8
