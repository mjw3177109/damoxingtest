#!/usr/bin/env python3
"""Offline, stdlib-only diagnostics for saved generation samples.

Does not load a model, contact Kaggle, or assert semantic/safety quality.
Reports aggregates without copying prompts or model output into the report.
"""
import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path


def longest_run(value: str) -> int:
    longest = current = 0
    previous = None
    for character in value:
        current = current + 1 if character == previous else 1
        longest = max(longest, current)
        previous = character
    return longest


def inspect_outputs(samples: list, source_sha256: str = "") -> dict:
    if not isinstance(samples, list):
        raise ValueError("samples.json must contain a list")
    rows = []
    outputs = []
    for index, item in enumerate(samples):
        if not isinstance(item, dict) or not isinstance(item.get("output"), str):
            raise ValueError(f"sample {index} must have a string output")
        output = item["output"].strip()
        outputs.append(output)
        counts = Counter(output)
        punctuation_only = bool(output) and all(unicodedata.category(c).startswith("P") for c in output)
        rows.append({
            "index": index,
            "characters": len(output),
            "distinct_characters": len(counts),
            "longest_identical_character_run": longest_run(output),
            "punctuation_only": punctuation_only,
            "single_character_repeated": bool(output) and len(counts) == 1,
        })
    return {
        "source_sha256": source_sha256,
        "sample_count": len(rows),
        "empty_output_count": sum(not output for output in outputs),
        "punctuation_only_count": sum(row["punctuation_only"] for row in rows),
        "single_character_repeated_count": sum(row["single_character_repeated"] for row in rows),
        "unique_output_count": len(set(outputs)),
        "longest_identical_character_run": max((row["longest_identical_character_run"] for row in rows), default=0),
        "rows": rows,
        "interpretation": "Lexical diagnostics only; not evidence of response correctness or safety. No new model inference was performed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path, help="Path to an existing samples.json")
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    args = parser.parse_args()
    data = args.samples.read_bytes()
    result = inspect_outputs(json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest())
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
