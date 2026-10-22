#!/usr/bin/env python3
"""Create Kaggle kernel metadata with a title whose slug exactly matches its ID."""
import argparse
import json
import re
from pathlib import Path

DEFAULT_SLUG = "damoxingtest-gpt-2-daily-training"
DEFAULT_TITLE = "Damoxingtest GPT-2 Daily Training"


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    args = parser.parse_args()

    username = args.username.strip()
    slug = args.slug.strip().lower()
    title = args.title.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", username):
        raise SystemExit("KAGGLE_USERNAME contains unsupported characters.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SystemExit("Kernel slug must contain lowercase letters, digits, and single hyphens.")
    generated_slug = slugify(title)
    if generated_slug != slug:
        raise SystemExit(
            "Kaggle title/ID mismatch: title slug is "
            + generated_slug
            + " but requested slug is "
            + slug
            + ". Change the title or slug so they match exactly."
        )

    metadata = {
        "id": username + "/" + slug,
        "title": title,
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
    # Read it back to catch accidental metadata corruption before the API call.
    written = json.loads(path.read_text(encoding="utf-8"))
    if written["id"].rsplit("/", 1)[-1] != slugify(written["title"]):
        raise SystemExit("Generated Kaggle metadata failed its title/ID consistency check.")

    print("Prepared private Kaggle kernel metadata.")
    print("Kernel ID:", username + "/" + slug)
    print("Title slug verified:", generated_slug)
    print("Credentials are not written to this file.")


if __name__ == "__main__":
    main()
