"""One-time no-GPU hold for the audited Run-12 inference-only edit.

This exact-byte pin does not waive training-recipe validation or reuse metrics.
Other revisions continue through the existing guarded Kaggle workflow.
"""
import hashlib
from pathlib import Path

# Audited historical GPU Run 39921870784 and isolated Draft PR #72.
EXPECTED_GIT_BLOBS = {
    "scripts/train_gpt2_lora.py": "52a63ac2324d997a2864901b5a1361e18b11603b",
    "kaggle/gpt2_training.ipynb": "6360b613f218cc8393ab93bb57dd679325cf0c65",
    "requirements-kaggle.txt": "af673e3fa207bc3c26727c4bcc4905378abd589d",
}
EXPECTED_DATA_SHA256 = {
    "data/safety_humanity_train_v2.jsonl": "ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c",
    "data/safety_humanity_eval_v1.jsonl": "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f",
}


def git_blob_sha(path):
    content = Path(path).read_bytes()
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return hashlib.sha1(header + content).hexdigest()


def should_hold_inference_only(repo_root):
    """True only for the exact audited inference-only snapshot."""
    root = Path(repo_root)
    try:
        return (
            all(git_blob_sha(root / path) == expected
                for path, expected in EXPECTED_GIT_BLOBS.items())
            and all(hashlib.sha256((root / path).read_bytes()).hexdigest() == expected
                    for path, expected in EXPECTED_DATA_SHA256.items())
        )
    except OSError:
        return False
