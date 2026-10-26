"""Aggregate-only corpus vs generation punctuation audit (stdlib, no GPU).

Never emits prompts, response text, or generated content. This is a diagnostic,
not a semantic quality or model safety certification.
"""

import argparse
import json
import unicodedata
from itertools import groupby
from pathlib import Path

PUNCTUATION = frozenset("。！？!?.,，、；;：:…·")


def is_punctuation_only(value):
    meaningful = [char for char in value if not char.isspace()]
    return bool(meaningful) and all(
        unicodedata.category(char).startswith(("P", "S")) for char in meaningful
    )


def max_punctuation_run(value):
    return max(
        (len(list(group)) for char, group in groupby(value) if char in PUNCTUATION),
        default=0,
    )


def summarize(values):
    values = list(values)
    total_chars = sum(len(value) for value in values)
    punctuation_chars = sum(sum(char in PUNCTUATION for char in value) for value in values)
    return {
        "count": len(values),
        "total_chars": total_chars,
        "punctuation_chars": punctuation_chars,
        "punctuation_ratio": round(punctuation_chars / total_chars, 6) if total_chars else None,
        "punctuation_only": sum(is_punctuation_only(value) for value in values),
        "starts_punctuation": sum(bool(value) and value[0] in PUNCTUATION for value in values),
        "max_identical_punctuation_run": max((max_punctuation_run(v) for v in values), default=0),
        "eight_plus_identical_punctuation_run": sum(max_punctuation_run(v) >= 8 for v in values),
        "unique_values": len(set(values)),
    }


def load_jsonl_answers(path):
    answers = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict) or not isinstance(record.get("response"), str):
            raise ValueError("JSONL record missing string response")
        answers.append(record["response"])
    return answers


def load_samples(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("samples.json must be a list")
    if not all(isinstance(record, dict) and isinstance(record.get("output"), str) for record in records):
        raise ValueError("sample record missing string output")
    return [record["output"] for record in records]


def audit(train_path, eval_path, samples_path):
    return {
        "method": "aggregate-only punctuation audit; no model inference or GPU",
        "punctuation_set": "。！？!?.,，、；;：:…·",
        "train_responses": summarize(load_jsonl_answers(train_path)),
        "eval_responses": summarize(load_jsonl_answers(eval_path)),
        "historical_samples": summarize(load_samples(samples_path)),
        "limitation": "Character statistics cannot establish causal origin of generation collapse.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--samples", required=True)
    parser.add_argument("--output", help="Optional aggregate JSON destination")
    args = parser.parse_args()
    result = audit(args.train, args.eval, args.samples)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
