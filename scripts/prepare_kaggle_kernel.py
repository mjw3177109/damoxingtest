#!/usr/bin/env python3
"""Create Kaggle kernel metadata from the username stored in GitHub Secrets."""
import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    username = args.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", username):
        raise SystemExit("KAGGLE_USERNAME contains unsupported characters.")

    metadata = {
        "id": username + "/damoxingtest-gpt2-daily",
        "title": "Damoxingtest GPT-2 Daily Training",
        "code_file": "gpt2_training.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
    }
    path = Path("kaggle/kernel-metadata.json")
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Prepared private Kaggle kernel metadata for the configured account.")
    print("Kernel slug: damoxingtest-gpt2-daily")
    print("Credentials are not written to this file.")


if __name__ == "__main__":
    main()