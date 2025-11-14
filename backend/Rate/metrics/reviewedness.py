# metrics/reviewedness.py
import re
import time
import os
import requests
from typing import Optional, Tuple


def reviewedness(model_url: str) -> Tuple[float, int]:
    """
    Estimate how much of the code in a linked GitHub repository
    was introduced through reviewed pull requests.
    If no GitHub repository can be found, return 0.
    """
    start_time = time.time_ns()

    #Read GitHub token from environment (NEEDS TO BE SET CONFIRM THIS)
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        #Try to locate a GitHub repository URL
        match = re.search(r"github\.com/([^/\s]+)/([^/\s/]+?)(?:\.git|/|$)", model_url)

        '''
        print(f"[DEBUG] Model URL: {model_url}")
        if match:
            print(f"[DEBUG] Found GitHub repo: {match.group(1)}/{match.group(2)}")
        else:
            print("[DEBUG] No GitHub repo found directly in URL. Trying to scrape page...")
        '''
        
        #if the model url passed in is not github then search page for a url (ASK BETTER WAY TO DO THIS WITH HUGGING FACE)
        if not match:
            try:
                #this loads the webpage and searches for the github url string 
                r = requests.get(model_url, timeout=10)
                if r.status_code == 200:
                    match = re.search(r"github\.com/([^/\s]+)/([^/\s/]+)", r.text)
            except Exception:
                pass

        #IF no github found then return 0 
        if not match:
            latency_ms = (time.time_ns() - start_time) // 1_000_000
            print("here3")
            return 0, latency_ms

        owner, repo = match.group(1), match.group(2)
        base_api = f"https://api.github.com/repos/{owner}/{repo}"

        #Retrieve pull requests from github (return 0 if cant) (only looking at 30 most recent right now)
        prs_url = f"{base_api}/pulls?state=closed&per_page=30"
        prs_response = requests.get(prs_url, headers=headers, timeout=10)
        if prs_response.status_code != 200:
            latency_ms = (time.time_ns() - start_time) // 1_000_000
            #print("here4")
            #print(f"[DEBUG] Failed to get PRs ({prs_url}) → status: {prs_response.status_code}")
            #print("[DEBUG] Response text:", prs_response.text[:300])
            return 0, latency_ms

        prs = prs_response.json()
        if not isinstance(prs, list) or len(prs) == 0:
            latency_ms = (time.time_ns() - start_time) // 1_000_000
            #print("here5")
            return 0, latency_ms

        total_added = 0
        reviewed_added = 0

        #print("here1")
        #Loop through each pull request and check 
        for pr in prs:
            #print("here2")
            
            #skip unmerged pull requests 
            if not pr.get("merged_at"):
                continue 

            pr_number = pr["number"]

            #Get reviers and comments from pull request
            pr_info = requests.get(f"{base_api}/pulls/{pr_number}", headers=headers, timeout=10)
            if pr_info.status_code != 200:
                continue
            pr_data = pr_info.json()

            #check if has at least one review comment or one requested reviewer 
            reviewed = bool(pr_data.get("review_comments", 0)) or bool(pr_data.get("requested_reviewers"))

            #get the files that were changed in pull request 
            files_url = f"{base_api}/pulls/{pr_number}/files"
            files_response = requests.get(files_url, headers=headers, timeout=10)
            if files_response.status_code != 200:
                continue
            files = files_response.json()

            #count added lines 
            for f in files:
                filename = f.get("filename", "").lower()

                #skip large binary files or anything wierd like model weights 
                if filename.endswith((".bin", ".safetensors", ".ckpt", ".pt", ".pth")):
                    continue  

                additions = f.get("additions", 0)
                total_added += additions
                if reviewed:
                    reviewed_added += additions

        #If there were no code additions at all return 0 
        if total_added == 0:
            latency_ms = (time.time_ns() - start_time) // 1_000_000
            return 0, latency_ms

        #calculate final score rounded to 3 decimal places (Ratio of lines reviewed over total lines)
        score = round(reviewed_added / total_added, 3)
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return score, latency_ms

    except Exception:
        latency_ms = (time.time_ns() - start_time) // 1_000_000
        return 0, latency_ms
