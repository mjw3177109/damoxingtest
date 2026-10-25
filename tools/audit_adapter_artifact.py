#!/usr/bin/env python3
"""Read-only evidence audit for a GPT-2 LoRA Actions artifact ZIP.

A present adapter is a recoverable *candidate*, never evidence of approval.
No archive extraction, model loading, Kaggle access, or secret handling.
"""
import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_CONFIG_BYTES = 256 * 1024
MAX_SAFETENSORS_HEADER_BYTES = 8 * 1024 * 1024
DTYPE_BYTES = {"BOOL": 1, "U8": 1, "I8": 1, "F8_E4M3": 1, "F8_E5M2": 1,
               "I16": 2, "U16": 2, "F16": 2, "BF16": 2, "I32": 4,
               "U32": 4, "F32": 4, "I64": 8, "U64": 8, "F64": 8}


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



def check_safetensors_header(zf: zipfile.ZipFile, path: str) -> int:
    """Validate bounded safetensors header and tensor ranges, without loading tensors.

    Does not prove that the adapter can be loaded by PEFT or the base model.
    """
    size = zf.getinfo(path).file_size
    if size == 0:
        raise ValueError("empty adapter weight file")
    if size < 10:
        raise ValueError("invalid safetensors: file too small")
    with zf.open(path) as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("invalid safetensors: missing header length")
        header_size = struct.unpack("<Q", prefix)[0]
        if not (2 <= header_size <= MAX_SAFETENSORS_HEADER_BYTES) or header_size > size - 8:
            raise ValueError("invalid safetensors: header length out of bounds")
        raw = stream.read(header_size)
        if len(raw) != header_size:
            raise ValueError("invalid safetensors: truncated header")
    try:
        header = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid safetensors: malformed header JSON") from exc
    if not isinstance(header, dict):
        raise ValueError("invalid safetensors: header must be an object")
    tensors = [(key, value) for key, value in header.items() if key != "__metadata__"]
    if not tensors:
        raise ValueError("invalid safetensors: no tensors")
    payload_size = size - 8 - header_size
    ranges = []
    for name, entry in tensors:
        if not isinstance(name, str) or not isinstance(entry, dict):
            raise ValueError("invalid safetensors: malformed tensor entry")
        dtype, shape, offsets = entry.get("dtype"), entry.get("shape"), entry.get("data_offsets")
        if not isinstance(dtype, str) or dtype not in DTYPE_BYTES or not isinstance(shape, list) or not isinstance(offsets, list) or len(offsets) != 2:
            raise ValueError("invalid safetensors: invalid tensor metadata")
        if any(type(dim) is not int or dim < 0 for dim in shape):
            raise ValueError("invalid safetensors: invalid tensor shape")
        start, end = offsets
        if type(start) is not int or type(end) is not int or not (0 <= start <= end <= payload_size):
            raise ValueError("invalid safetensors: tensor offsets out of bounds")
        elements = 1
        for dim in shape:
            elements *= dim
            if elements > payload_size:
                raise ValueError("invalid safetensors: tensor shape exceeds payload")
        if end - start != elements * DTYPE_BYTES[dtype]:
            raise ValueError("invalid safetensors: tensor size mismatch")
        ranges.append((start, end))
    ranges.sort()
    cursor = 0
    for start, end in ranges:
        if start != cursor:
            raise ValueError("invalid safetensors: tensor ranges overlap or leave gaps")
        cursor = end
    if cursor != payload_size:
        raise ValueError("invalid safetensors: trailing unindexed data")
    return len(tensors)


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
        tensor_count = check_safetensors_header(zf, weights)
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
                "safetensors_header_check": "passed", "tensor_count": tensor_count,
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
