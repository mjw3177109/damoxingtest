#!/usr/bin/env python3
"""Read-only character bigram audit for train/holdout near-duplicates.

No model downloads, network, GPU, or raw record text in JSON output. This
is a screening heuristic, not proof of semantic equivalence or contamination.
"""
import argparse
import json
import unicodedata
from pathlib import Path


def normalized(text):
    return "".join(char.lower() for char in unicodedata.normalize("NFKC", text) if char.isalnum())


def bigrams(text):
    chars = normalized(text)
    return {chars[i:i + 2] for i in range(max(0, len(chars) - 1))}


def jaccard(left, right):
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right) if left or right else 0.0


def read_jsonl(path):
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("instruction", "response")):
            raise ValueError(f"Invalid instruction/response at line {line_number}")
        records.append((line_number, item))
    return records


def audit(train_records, eval_records, instruction_threshold=0.65, response_threshold=0.80):
    """Return only line numbers and similarity scores, never record text."""
    train = [(number, bigrams(row["instruction"]), bigrams(row["response"])) for number, row in train_records]
    evals = [(number, bigrams(row["instruction"]), bigrams(row["response"])) for number, row in eval_records]
    matches = []
    for eval_line, eval_instruction, eval_response in evals:
        for train_line, train_instruction, train_response in train:
            instruction_score = jaccard(eval_instruction, train_instruction)
            if instruction_score < instruction_threshold:
                continue
            response_score = jaccard(eval_response, train_response)
            if response_score >= response_threshold:
                matches.append({
                    "train_line": train_line,
                    "eval_line": eval_line,
                    "instruction_bigram_jaccard": round(instruction_score, 6),
                    "response_bigram_jaccard": round(response_score, 6),
                })
    return {
        "train_records": len(train),
        "eval_records": len(evals),
        "pair_count": len(train) * len(evals),
        "instruction_threshold": instruction_threshold,
        "response_threshold": response_threshold,
        "near_duplicate_pairs": sorted(matches, key=lambda row: (row["eval_line"], row["train_line"])),
        "warning": "Heuristic overlap screening only; do not treat this holdout as fully independent without review." if matches else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--instruction-threshold", type=float, default=0.65)
    parser.add_argument("--response-threshold", type=float, default=0.80)
    parser.add_argument("--strict", action="store_true", help="Exit 2 if suspicious pairs exist; never change source data")
    args = parser.parse_args(argv)
    if not all(0 <= threshold <= 1 for threshold in (args.instruction_threshold, args.response_threshold)):
        parser.error("Thresholds must be in [0, 1]")
    result = audit(read_jsonl(args.train), read_jsonl(args.eval), args.instruction_threshold, args.response_threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.strict and result["near_duplicate_pairs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
