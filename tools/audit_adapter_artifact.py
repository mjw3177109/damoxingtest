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

MAX_CONFIG_BYTES = 256 * 1024


def check_adapter_config(zf: zipfile.ZipFile, path: str, expected_base_model: str | None) -> str:
    """Check bounded JSON metadata without executing code or revealing model paths."""
    info = zf.getinfo(path)
    if info.file_size > MAX_CONFIG_BYTES:
        raise ValueError("adapter config exceeds size limit")
    try:
        config = json.loads(zf.read(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("adapter config is not valid JSON") from exc
    if not isinstance(config, dict):
        raise ValueError("adapter config must be a JSON object")
    model = config.get("base_model_name_or_path")
    if model is not None and (not isinstance(model, str) or not model or len(model) > 512):
        raise ValueError("adapter config has invalid base model metadata")
    if expected_base_model is None:
        return "not_checked"
    if model is None:
        return "missing"
    return "matched" if model == expected_base_model else "mismatched"


def audit_artifact(archive: Path, run_id: str, expected_base_model: str | None = None) -> dict:
    """Verify ZIP integrity and candidate metadata; never approve a model."""
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
        config_path = str(PurePosixPath(weights).parent / "adapter_config.json")
        base_model_status = check_adapter_config(zf, config_path, expected_base_model)
        with zf.open(weights) as stream:
            digest = hashlib.sha256()
            byte_count = 0
            while block := stream.read(1024 * 1024):
                digest.update(block)
                byte_count += len(block)
        if byte_count == 0:
            raise ValueError("empty adapter weight file")
        base_ok = base_model_status in ("matched", "not_checked")
        return {"run_id": run_id, "archive_integrity": "passed",
                "adapter_present": True, "candidate_recoverable": base_ok,
                "adapter_bytes": byte_count, "adapter_sha256": digest.hexdigest(),
                "base_model_check": base_model_status,
                "approval_verified": False,
                "reason": ("expected base model not verified" if not base_ok else
                           "artifact integrity is not an independent approval or durable rollback guarantee")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-base-model", help="Optional exact expected base model ID")
    args = parser.parse_args(argv)
    try:
        result = audit_artifact(args.archive, args.run_id, args.expected_base_model)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"run_id": args.run_id, "archive_integrity": "failed",
                          "adapter_present": False, "candidate_recoverable": False,
                          "approval_verified": False, "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["candidate_recoverable"] else 2


if __name__ == "__main__":
    sys.exit(main())
