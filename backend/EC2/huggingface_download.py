import os
import re
import json
import shutil
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

# ===============================
# Source Detection
# ===============================
def detect_source(url: str) -> str:
    if "huggingface.co" in url:
        return "huggingface"
    if "github.com" in url:
        return "github"
    raise ValueError(f"Unsupported URL: {url}")

# ===============================
# HuggingFace Downloader
# ===============================
def download_huggingface(url, artifact_id, artifact_type):
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

# ===============================
# GitHub Downloader
# ===============================
def download_github(url, artifact_id):
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

# ===============================
# Zip Directory
# ===============================
def zip_directory(src_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(src_dir):
            for file in files:
                full = os.path.join(root, file)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)

# ===============================
# Main Router
# ===============================
def process_url(url, artifact_id, artifact_type):
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

