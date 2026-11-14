#!/usr/bin/env python3
"""Recheck paired lexical diagnostics from a prior CPU Artifact; no model inference.

Consumes only the numeric reference_overlap.json schema. Never prints prompts,
references, generated text, token IDs, or model credentials.
"""
import argparse
import json
import math
from pathlib import Path

ARMS = ("base", "run12_candidate")


def summarize_pairs(rows):
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("Expected exactly 20 numeric rows (10 per arm)")
    pairs = {arm: {} for arm in ARMS}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Expected numeric row objects")
        arm, index, digest = (row.get(key) for key in ("arm", "prompt_index", "prompt_sha256"))
        if arm not in pairs or type(index) is not int or not 0 <= index < 10:
            raise ValueError("Invalid arm or prompt index")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid prompt provenance")
        if index in pairs[arm]:
            raise ValueError("Duplicate prompt index")
        f1, length, stop = (row.get(key) for key in ("char_bigram_f1", "output_char_count", "stop_reason_inferred"))
        if type(f1) not in (float, int) or not math.isfinite(f1) or not 0 <= f1 <= 1:
            raise ValueError("Invalid lexical score")
        if type(length) is not int or length < 0:
            raise ValueError("Invalid output length")
        if stop not in ("eos", "max_new_tokens"):
            raise ValueError("Invalid stopping reason")
        pairs[arm][index] = row
    if any(set(pairs[arm]) != set(range(10)) for arm in ARMS):
        raise ValueError("Missing paired prompt")
    better = worse = tied = changed_length = changed_eos = 0
    for index in range(10):
        base, candidate = (pairs[arm][index] for arm in ARMS)
        if base["prompt_sha256"] != candidate["prompt_sha256"]:
            raise ValueError("Unpaired prompt hashes")
        delta = candidate["char_bigram_f1"] - base["char_bigram_f1"]
        better += delta > 0
        worse += delta < 0
        tied += delta == 0
        changed_length += base["output_char_count"] != candidate["output_char_count"]
        changed_eos += (base["stop_reason_inferred"] == "eos") != (candidate["stop_reason_inferred"] == "eos")
    return {
        "paired_prompts": 10,
        "candidate_better_bigram_f1": better,
        "candidate_worse_bigram_f1": worse,
        "tied_bigram_f1": tied,
        "output_character_length_changed": changed_length,
        "eos_status_changed": changed_eos,
        "semantic_quality_assessed": False,
        "promotion_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_json", type=Path, help="Extracted reference_overlap.json from a verified Artifact")
    args = parser.parse_args()
    data = json.loads(args.artifact_json.read_text(encoding="utf-8"))
    result = summarize_pairs(data["per_prompt_numeric_diagnostics"])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
