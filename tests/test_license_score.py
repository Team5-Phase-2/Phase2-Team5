# tests/test_license_score.py

import pytest
from unittest.mock import MagicMock
import time

from backend.Rate.metrics.license_score import license_score
from backend.Rate.metrics import license_score as ls


def test_http_model_id_returns_zero(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "http://bad")

    score, latency = license_score("x", "y", "z")
    assert score == 0.0
    assert isinstance(latency, int)


def test_empty_readme_returns_zero(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(ls, "fetch_hf_readme_text", lambda _: "")

    score, _ = license_score("x", "y", "z")
    assert score == 0.0


def test_restrictive_license_returns_zero(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: "This project is licensed under GPLv3",
    )

    score, _ = license_score("x", "y", "z")
    assert score == 0.0


def test_unclear_license_returns_half(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: "Licensed under the OpenRAIL license",
    )

    score, _ = license_score("x", "y", "z")
    assert score == 0.5


def test_permissive_license_returns_one(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: "MIT License",
    )

    score, _ = license_score("x", "y", "z")
    assert score == 1.0




def test_license_header_parsing(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: "License: Apache 2.0",
    )

    score, _ = license_score("x", "y", "z")
    assert score == 1.0


def test_license_section_parsing(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: """
        ## License
        BSD-3-Clause
        """,
    )

    score, _ = license_score("x", "y", "z")
    assert score == 1.0


def test_fallback_to_full_readme(monkeypatch):
    monkeypatch.setattr(ls, "_hf_model_id_from_url", lambda _: "owner/repo")
    monkeypatch.setattr(
        ls,
        "fetch_hf_readme_text",
        lambda _: "This model is released under CC-BY-4.0",
    )

    score, _ = license_score("x", "y", "z")
    assert score == 1.0



