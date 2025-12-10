# metrics/reviewedness.py
import re
import time
import os
import requests
from typing import Tuple


def reviewedness(model_url: str, code_url: str, dataset_url: str) -> Tuple[float, int]:
    """
    Computes the reviewedness metric for a models GitHub repository, as required
    by the Phase 2 specification.

    The function:
      1. Identifies the GitHub repo from either a direct URL or a HuggingFace page.
      2. Fetches up to 30 recent closed pull requests.
      3. Determines which PRs received code reviews.
      4. Counts added lines across reviewed vs. unreviewed PRs.
      5. Returns the ratio of reviewed additions to total additions.

    Args:
        model_url (str): GitHub or HuggingFace model URL.

    Returns:
        Tuple[float, int]:
            - reviewedness score (0-1, or -1 if no repo found)
            - total latency in milliseconds
    """

    #print("\n>>")
    #print("[DEBUG] Checking URL:", model_url)

    #Start timer
    start_time = time.time_ns()

    #Set up GitHub API headers
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    #Extract GitHub repo from URL
    def extract_github_repo(text: str):
        match = re.search(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text)
        if match:
            #print("[DEBUG] Extracted GitHub repo from text:", match.group(0))
            return match.group(1), match.group(2)
        return None

    # Find GitHub repo from HuggingFace HTML
    def find_github_repo_from_hf_html(model_url: str):
        #print("[DEBUG] Fetching HF HTML:", model_url)

        #Get Model Card from HuggingFace
        try:
            resp = requests.get(model_url, timeout=10)
            html = resp.text
            #print("[DEBUG] HF HTML status:", resp.status_code)
        except Exception as e:
            #print("[DEBUG] HF HTML failed:", e)
            return None

        #GitHub repo links
        patterns = [
            r'https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)',
            r'github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)',
            r'href="https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)'
        ]

        #Look for GitHub repo links
        for p in patterns:
            match = re.search(p, html)
            if match:
                #print("[DEBUG] Found GitHub via pattern:", match.group(0))
                return match.group(1), match.group(2)

        #print("[DEBUG] No GitHub link found in HF HTML.")
        return None

    #First Check URL is github link
    owner_repo = extract_github_repo(model_url)

    #Second Check huggingface
    if not owner_repo and "huggingface.co" in model_url:
        owner_repo = find_github_repo_from_hf_html(model_url)

   #If link is not found, return -1
    if not owner_repo:
        #print("[DEBUG] No GitHub repo found → returning -1")
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return -1, latency_ms

    #print("[DEBUG] Final extracted repo:", owner_repo)

    owner, repo = owner_repo
    base_api = f"https://api.github.com/repos/{owner}/{repo}"

    #Set up check for pull requests
    MAX_PRS = 30
    prs_url = (
        f"{base_api}/pulls?state=closed&per_page={MAX_PRS}&sort=updated&direction=desc"
    )
    #print("[DEBUG] Fetching PR list:", prs_url)

    #Check pull requests
    prs_resp = requests.get(prs_url, headers=headers, timeout=10)
    if prs_resp.status_code != 200:
        #print("[DEBUG] Failed to fetch PRs:", prs_resp.status_code)
        #if failed to get PRs return -1
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return -1, latency_ms

    prs = prs_resp.json()
    #print("[DEBUG] PR count:", len(prs))

    #if not closed PRs return -1
    if not prs:
        print("[DEBUG] Zero PRs found.")
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return -1, latency_ms

    #tracker variables
    total_added = 0
    reviewed_added = 0
    binary_exts = (".bin", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx")

    #check each PR to see if reviewed
    for pr in prs:
        if not pr.get("merged_at"):
            continue

        pr_number = pr["number"]

        #get reviews
        reviews_url = f"{base_api}/pulls/{pr_number}/reviews"
        rev_resp = requests.get(reviews_url, headers=headers, timeout=10)
        reviews = rev_resp.json() if rev_resp.status_code == 200 else []
        reviewed = len(reviews) > 0

        #get file changes
        files_url = f"{base_api}/pulls/{pr_number}/files"
        files_resp = requests.get(files_url, headers=headers, timeout=10)
        files = files_resp.json() if files_resp.status_code == 200 else []

        #for each file check if reviewed
        for f in files:
            fname = f.get("filename", "").lower()
            additions = f.get("additions", 0)

            #skip binary files
            if fname.endswith(binary_exts):
                continue

            total_added += additions
            if reviewed:
                reviewed_added += additions

    #compute score
    if total_added == 0:
        #print("[DEBUG] No code additions found.")
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return 0, latency_ms

    score = round(reviewed_added / total_added, 3)
    #print("[DEBUG] FINAL SCORE:", score)

    latency_ms = (time.time_ns() - start_time) // 1_000_000
    return score, latency_ms
