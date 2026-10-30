"""Audit archived LoRA safetensors using only Python stdlib (no GPU or model).

Only aggregated statistics are emitted; never logs raw tensor values, prompts,
weights, credentials or private data. Fails closed for unsupported dtypes.
"""

import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

MAX_WEIGHT_BYTES = 100 * 1024 * 1024


def audit_safetensors(data):
    if len(data) < 9 or len(data) > MAX_WEIGHT_BYTES:
        raise ValueError("Invalid or oversized adapter weight file")
    header_len = struct.unpack("<Q", data[:8])[0]
    if not 2 <= header_len <= 1024 * 1024 or 8 + header_len > len(data):
        raise ValueError("Invalid safetensors header length")
    header = json.loads(data[8:8 + header_len].decode("utf-8"))
    if not isinstance(header, dict):
        raise ValueError("Invalid safetensors header")
    payload = memoryview(data)[8 + header_len:]
    ranges = []
    count = 0
    parameters = 0
    nonfinite = 0
    zero_tensors = 0
    min_norm = float("inf")
    max_norm = 0.0
    for name, info in header.items():
        if name == "__metadata__":
            continue
        if not isinstance(info, dict) or info.get("dtype") != "F32":
            raise ValueError("Only F32 adapter tensors are supported")
        shape = info.get("shape")
        offsets = info.get("data_offsets")
        if not isinstance(shape, list) or not shape or any(not isinstance(dim, int) or dim <= 0 for dim in shape):
            raise ValueError("Invalid tensor shape")
        if not isinstance(offsets, list) or len(offsets) != 2 or any(not isinstance(x, int) for x in offsets):
            raise ValueError("Invalid tensor offsets")
        start, end = offsets
        numel = math.prod(shape)
        if start < 0 or end > len(payload) or end - start != numel * 4:
            raise ValueError("Tensor data size or offset mismatch")
        ranges.append((start, end))
        squared = 0.0
        all_zero = True
        tensor_nonfinite = 0
        for (value,) in struct.iter_unpack("<f", payload[start:end]):
            if not math.isfinite(value):
                nonfinite += 1
                tensor_nonfinite += 1
                continue
            squared += value * value
            if value != 0:
                all_zero = False
        norm = math.sqrt(squared)
        min_norm = min(min_norm, norm)
        max_norm = max(max_norm, norm)
        zero_tensors += int(all_zero and tensor_nonfinite == 0)
        count += 1
        parameters += numel
    if not count:
        raise ValueError("Adapter has no tensors")
    ranges.sort()
    if ranges[0][0] != 0 or ranges[-1][1] != len(payload) or any(a[1] != b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError("Safetensors offsets overlap or leave gaps")
    return {
        "tensor_count": count,
        "parameter_count": parameters,
        "nonfinite_value_count": nonfinite,
        "all_zero_tensor_count": zero_tensors,
        "min_tensor_l2_norm": round(min_norm, 6),
        "max_tensor_l2_norm": round(max_norm, 6),
        "all_values_finite": nonfinite == 0,
    }


def audit_archive(path):
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith("/adapter/adapter_model.safetensors")]
        if len(names) != 1:
            raise ValueError("Archive must contain exactly one archived adapter weight file")
        info = archive.getinfo(names[0])
        if info.file_size > MAX_WEIGHT_BYTES:
            raise ValueError("Adapter weights exceed audit size limit")
        weights = archive.read(info)
    result = audit_safetensors(weights)
    result.update({
        "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "adapter_sha256": hashlib.sha256(weights).hexdigest(),
        "method": "Read-only F32 safetensors integrity audit; no GPU, inference or training",
        "limitation": "Finite, nonzero weights do not establish generation quality or model safety.",
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-zip", required=True)
    parser.add_argument("--output", help="Optional aggregate-only JSON path")
    args = parser.parse_args()
    result = audit_archive(args.artifact_zip)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
