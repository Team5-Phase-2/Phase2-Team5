"""Unit tests for the Reviewedness metric.

Tests code review quality by analyzing GitHub pull requests,
reviews, and file changes for models and code repositories.
"""

"Unit Tests for the Reviewedness metric"

import pytest
import backend.Rate.metrics.reviewedness as rv


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else []
        self.text = text

    def json(self):
        return self._json


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Centralized mock for requests.get.
    Tests register exact URLs -> MockResponse (or a callable).
    If you forget to stub a URL, the test fails loudly.
    """
    calls = {}

    def fake_get(url, *args, **kwargs):
        if url not in calls:
            raise AssertionError(f"Unmocked requests.get URL: {url}")
        val = calls[url]
        return val(url, *args, **kwargs) if callable(val) else val

    monkeypatch.setattr(rv.requests, "get", fake_get)
    return calls


def _prs_url(owner="owner", repo="repo"):
    return (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/pulls?state=closed&per_page=30&sort=updated&direction=desc"
    )


def _base(owner="owner", repo="repo"):
    return f"https://api.github.com/repos/{owner}/{repo}"


def test_no_github_repo_found_returns_minus_one():
    """Non-GitHub URL should return score of -1."""
    # Not github, not huggingface -> no extraction attempts -> -1
    score, latency = rv.reviewedness("https://example.com/not/github", "code", "data")
    assert score == -1
    assert isinstance(latency, int)


def test_hf_html_request_exception_returns_minus_one(monkeypatch):
    """Hugging Face HTML fetch error should return score of -1."""
    # Force HF fetch to raise, triggering the except path in find_github_repo_from_hf_html
    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(rv.requests, "get", boom)

    score, latency = rv.reviewedness("https://huggingface.co/some/model", "code", "data")
    assert score == -1
    assert isinstance(latency, int)


def test_hf_html_extracts_repo_and_scores_one(monkeypatch, mock_requests):
    """Hugging Face HTML with GitHub link should extract repo and score well."""
    monkeypatch.setenv("GITHUB_TOKEN", "dummy_token")

    model_url = "https://huggingface.co/some/model"
    # Use the href="https://github.com/..." pattern specifically (one of the patterns list)
    mock_requests[model_url] = MockResponse(
        text='... href="https://github.com/owner/repo" ...'
    )

    base = _base("owner", "repo")
    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[{"number": 1, "merged_at": "yes"}],
    )
    mock_requests[f"{base}/pulls/1/reviews"] = MockResponse(
        status_code=200, json_data=[{"id": 123}]
    )
    mock_requests[f"{base}/pulls/1/files"] = MockResponse(
        status_code=200, json_data=[{"filename": "x.py", "additions": 10}]
    )

    score, latency = rv.reviewedness(model_url, "code", "data")
    assert score == 1.0
    assert isinstance(latency, int)


def test_pr_api_failure_returns_minus_one(mock_requests):
    """GitHub API failure should return score of -1."""
    mock_requests[_prs_url("owner", "repo")] = MockResponse(status_code=500)

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == -1
    assert isinstance(latency, int)


def test_no_prs_returns_minus_one(mock_requests):
    mock_requests[_prs_url("owner", "repo")] = MockResponse(status_code=200, json_data=[])

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == -1
    assert isinstance(latency, int)


def test_skips_unmerged_prs_and_only_counts_merged(mock_requests):
    # Covers the branch:
    # if not pr.get("merged_at"): continue
    base = _base("owner", "repo")
    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[
            {"number": 1, "merged_at": None},     # should be skipped entirely
            {"number": 2, "merged_at": "yes"},    # counted
        ],
    )

    mock_requests[f"{base}/pulls/2/reviews"] = MockResponse(status_code=200, json_data=[{"id": 1}])
    mock_requests[f"{base}/pulls/2/files"] = MockResponse(
        status_code=200,
        json_data=[{"filename": "a.py", "additions": 50}],
    )

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == 1.0
    assert isinstance(latency, int)


def test_unreviewed_prs_returns_zero(mock_requests):
    base = _base("owner", "repo")

    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[{"number": 1, "merged_at": "yes"}],
    )
    mock_requests[f"{base}/pulls/1/reviews"] = MockResponse(status_code=200, json_data=[])
    mock_requests[f"{base}/pulls/1/files"] = MockResponse(
        status_code=200,
        json_data=[{"filename": "file.py", "additions": 10}],
    )

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == 0
    assert isinstance(latency, int)


def test_reviewed_and_unreviewed_ratio(mock_requests):
    base = _base("owner", "repo")

    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[
            {"number": 1, "merged_at": "yes"},
            {"number": 2, "merged_at": "yes"},
        ],
    )

    # PR 1 reviewed (30)
    mock_requests[f"{base}/pulls/1/reviews"] = MockResponse(status_code=200, json_data=[{"id": 1}])
    mock_requests[f"{base}/pulls/1/files"] = MockResponse(
        status_code=200,
        json_data=[{"filename": "a.py", "additions": 30}],
    )

    # PR 2 not reviewed (70)
    mock_requests[f"{base}/pulls/2/reviews"] = MockResponse(status_code=200, json_data=[])
    mock_requests[f"{base}/pulls/2/files"] = MockResponse(
        status_code=200,
        json_data=[{"filename": "b.py", "additions": 70}],
    )

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == pytest.approx(0.3, rel=1e-3)
    assert isinstance(latency, int)


def test_binary_files_are_ignored_and_total_added_zero_branch(mock_requests):
    # Covers:
    # - binary skipping
    # - total_added == 0 return branch (if ALL files are binary)
    base = _base("owner", "repo")

    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[{"number": 1, "merged_at": "yes"}],
    )
    mock_requests[f"{base}/pulls/1/reviews"] = MockResponse(status_code=200, json_data=[{"id": 1}])
    mock_requests[f"{base}/pulls/1/files"] = MockResponse(
        status_code=200,
        json_data=[
            {"filename": "model.bin", "additions": 100},
            {"filename": "weights.safetensors", "additions": 200},
        ],
    )

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == 0  # total_added stayed 0 because all were binary
    assert isinstance(latency, int)


def test_reviews_or_files_non_200_treated_as_empty(mock_requests):
    # Covers:
    # reviews status != 200 -> []
    # files status != 200 -> []
    # and thus total_added == 0 -> returns 0
    base = _base("owner", "repo")

    mock_requests[_prs_url("owner", "repo")] = MockResponse(
        status_code=200,
        json_data=[{"number": 1, "merged_at": "yes"}],
    )
    mock_requests[f"{base}/pulls/1/reviews"] = MockResponse(status_code=500, json_data=[{"id": 1}])
    mock_requests[f"{base}/pulls/1/files"] = MockResponse(status_code=500, json_data=[{"filename": "a.py", "additions": 10}])

    score, latency = rv.reviewedness("https://github.com/owner/repo", "code", "data")
    assert score == 0
    assert isinstance(latency, int)
