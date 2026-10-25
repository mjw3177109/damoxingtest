#!/usr/bin/env python3
"""Read-only evidence audit for a GPT-2 LoRA Actions artifact ZIP.

A present adapter is a recoverable *candidate*, never evidence of approval.
No archive extraction, model loading, Kaggle access, or secret handling.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath


def audit_artifact(archive: Path, run_id: str) -> dict:
    """Verify ZIP integrity and the candidate adapter files; never approve."""
    with zipfile.ZipFile(archive) as zf:
        members = zf.namelist()
        if len(members) != len(set(members)):
            raise ValueError("duplicate ZIP member paths")
        for name in members:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("unsafe ZIP member path")
        bad = zf.testzip()
        if bad is not None:
            raise ValueError("corrupt ZIP member")
        weight_paths = [n for n in members if n.endswith("/adapter/adapter_model.safetensors")]
        valid = [n for n in weight_paths if str(PurePosixPath(n).parent / "adapter_config.json") in members]
        if len(valid) != 1 or len(weight_paths) != 1:
            return {"run_id": run_id, "archive_integrity": "passed",
                    "adapter_present": False, "candidate_recoverable": False,
                    "approval_verified": False, "reason": "expected exactly one adapter weight and matching config"}
        weights = valid[0]
        with zf.open(weights) as stream:
            digest = hashlib.sha256()
            byte_count = 0
            while block := stream.read(1024 * 1024):
                digest.update(block)
                byte_count += len(block)
        if byte_count == 0:
            raise ValueError("empty adapter weight file")
        return {"run_id": run_id, "archive_integrity": "passed",
                "adapter_present": True, "candidate_recoverable": True,
                "adapter_bytes": byte_count, "adapter_sha256": digest.hexdigest(),
                "approval_verified": False,
                "reason": "artifact integrity is not an independent approval or durable rollback guarantee"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_artifact(args.archive, args.run_id)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"run_id": args.run_id, "archive_integrity": "failed",
                          "adapter_present": False, "candidate_recoverable": False,
                          "approval_verified": False, "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["candidate_recoverable"] else 2


if __name__ == "__main__":
    sys.exit(main())
