"""
Artifact Ingestion and S3 Upload Utility.

This script automates the retrieval of code repositories, models, or datasets from
external sources (HuggingFace or GitHub), bundles them into a ZIP archive, and
uploads the result to a specified AWS S3 bucket.

Workflow:
1.  **Configuration:** Retrieves the S3 bucket name and HuggingFace token from AWS Systems Manager (SSM) Parameter Store in `us-east-2`.
2.  **Source Detection:** Identifies if the provided URL belongs to HuggingFace or GitHub.
3.  **Download:**
    -   **HuggingFace:** Uses `snapshot_download` to retrieve models or datasets. Parses the URL to determine the repository type.
    -   **GitHub:** Resolves the default branch via API and streams the repository archive as a ZIP file.
4.  **Compression:** If the download results in a raw directory, it is compressed into a ZIP file.
5.  **Upload:** The artifact is uploaded to S3 using the key pattern: `artifacts/{artifact_type}/{artifact_id}/artifact.zip`.
6.  **Output:** Prints a JSON object containing the status and S3 location.

Arguments:
    --url           : Full URL to the source (e.g., https://huggingface.co/meta-llama/Llama-2-7b).
    --artifact_id   : Unique identifier used for file naming and S3 paths.
    --artifact_type : Category string (e.g., 'model', 'dataset', 'code') used in the S3 key.
"""

import os
import re
import json
import zipfile
import requests
from urllib.parse import urlparse

import boto3
from huggingface_hub import snapshot_download

# ===============================
# Configuration
# ===============================
REGION = "us-east-2"
WORK_DIR = "/mnt/nvme"
os.makedirs(WORK_DIR, exist_ok=True)

# ===============================
# AWS Clients
# ===============================
ssm = boto3.client("ssm", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

S3_BUCKET = ssm.get_parameter(
    Name="/myapp/s3_bucket"
)["Parameter"]["Value"]

HF_TOKEN = ssm.get_parameter(
    Name="/hf/token",
    WithDecryption=True
)["Parameter"]["Value"]

def detect_source(url: str) -> str:
    """Identify the source platform based on the provided URL.

    Checks the URL against supported domains (HuggingFace, GitHub) to return
    the specific source type. Raises a ValueError if the domain is unsupported.
    """
    if "huggingface.co" in url:
        return "huggingface"
    if "github.com" in url:
        return "github"
    raise ValueError(f"Unsupported URL: {url}")

def download_huggingface(url, artifact_id, artifact_type):
    """Download a repository snapshot from HuggingFace.

    Parses the URL to determine if the target is a model or dataset, then uses
    `snapshot_download` to fetch the repository contents to a local directory.
    """
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")

    if parts[0] == "datasets":
        repo_type = "dataset"
        repo_id = "/".join(parts[1:3])
    else:
        repo_type = "model"
        repo_id = "/".join(parts[0:2])

    local_dir = os.path.join(WORK_DIR, f"{artifact_id}_repo")

    return snapshot_download(
        repo_id=repo_id,
        repo_type=repo_type,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        cache_dir=os.path.join(WORK_DIR, "hf_cache"),
        token=HF_TOKEN,
    )

def download_github(url, artifact_id):
    """Download a GitHub repository as a ZIP archive.

    Queries the GitHub API to identify the default branch, then streams the
    source code archive directly to a local ZIP file to minimize disk usage.
    """   
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)", url)
    if not m:
        raise ValueError("Invalid GitHub URL")

    owner, repo = m.groups()

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    info = requests.get(api_url, timeout=10).json()
    branch = info.get("default_branch", "main")

    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
    local_zip = os.path.join(WORK_DIR, f"{artifact_id}.zip")

    with requests.get(zip_url, stream=True) as r:
        r.raise_for_status()
        with open(local_zip, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)

    return local_zip

def zip_directory(src_dir, zip_path):
    """Recursively compress a local directory into a ZIP file.

    Walks the source directory tree and adds files to the archive using relative
    paths to maintain the internal folder structure.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                full = os.path.join(root, file)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)

def process_url(url, artifact_id, artifact_type):
    """Orchestrate the artifact download, compression, and S3 upload.

    Routes the URL to the appropriate downloader, ensures the final output is
    compressed, uploads it to the S3 bucket, and returns the object metadata.
    """
    source = detect_source(url)
    zip_path = os.path.join(WORK_DIR, f"{artifact_id}.zip")

    if source == "huggingface":
        folder = download_huggingface(url, artifact_id, artifact_type)
        zip_directory(folder, zip_path)

    elif source == "github":
        zip_path = download_github(url, artifact_id)

    s3_key = f"artifacts/{artifact_type}/{artifact_id}/artifact.zip"
    s3.upload_file(zip_path, S3_BUCKET, s3_key)

    return {
        "status": "ok",
        "bucket": S3_BUCKET,
        "key": s3_key,
    }

# ===============================
# CLI Entry (SSM-friendly)
# ===============================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--artifact_id", required=True)
    parser.add_argument("--artifact_type", required=True)
    args = parser.parse_args()

    result = process_url(
        args.url,
        args.artifact_id,
        args.artifact_type
    )

    print(json.dumps(result))
