#!/usr/bin/env python3
"""Read-only CPU audit of Run 12 EOS supervision using its saved tokenizer.

No model inference, GPU, training, raw instructions, responses, or token IDs are exported.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

TRAIN_SHA = "ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c"
EVAL_SHA = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"
SOURCE_RUN_ID = 39921870784


def load_pinned(path, expected_sha):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ValueError("Data SHA-256 mismatch; refusing non-comparable audit")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not rows or any(not isinstance(r, dict) or not isinstance(r.get("instruction"), str)
                       or not r["instruction"].strip() or not isinstance(r.get("response"), str)
                       or not r["response"].strip() for r in rows):
        raise ValueError("Invalid instruction/response records")
    return rows, digest


def audit_rows(records, tokenizer, max_length):
    if not isinstance(max_length, int) or max_length < 2:
        raise ValueError("max_length must be at least two")
    eos_id = tokenizer.eos_token_id
    if eos_id is None or not tokenizer.eos_token:
        raise ValueError("Tokenizer EOS missing")
    answer_sizes = []
    prefix_sizes = []
    truncated = missing_eos = eos_in_answer_not_terminal = no_supervision = supervised_eos = 0
    for record in records:
        prefix = "用户：" + record["instruction"] + "\n助手："
        answer = record["response"] + str(tokenizer.eos_token)
        prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
        kept = (prefix_ids + answer_ids)[:max_length]
        labels = ([-100] * len(prefix_ids) + answer_ids)[:max_length]
        supervised = [value for value in labels if value != -100]
        prefix_sizes.append(len(prefix_ids))
        answer_sizes.append(len(answer_ids))
        no_supervision += not bool(supervised)
        missing_eos += not bool(answer_ids) or answer_ids[-1] != eos_id
        eos_in_answer_not_terminal += bool(answer_ids) and eos_id in answer_ids[:-1]
        truncated += len(kept) < len(prefix_ids) + len(answer_ids)
        supervised_eos += bool(supervised) and supervised[-1] == eos_id and len(kept) == len(prefix_ids) + len(answer_ids)
        if len(labels) != len(kept):
            raise AssertionError("Label/input alignment mismatch")
    return {
        "records": len(records),
        "max_length": max_length,
        "eos_id_present": True,
        "answer_terminal_eos_missing_count": int(missing_eos),
        "answer_internal_eos_count": int(eos_in_answer_not_terminal),
        "records_truncated_count": int(truncated),
        "records_without_supervised_tokens": int(no_supervision),
        "prefix_tokens_min_median_max": [min(prefix_sizes), median(prefix_sizes), max(prefix_sizes)],
        "answer_tokens_min_median_max": [min(answer_sizes), median(answer_sizes), max(answer_sizes)],
        "terminal_eos_supervised_count": int(supervised_eos),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--train-data", type=Path, default=Path("data/safety_humanity_train_v2.jsonl"))
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.tokenizer_dir / "tokenizer_config.json").is_file():
        parser.error("Saved Run 12 tokenizer_config.json is required; no fallback")
    train, train_sha = load_pinned(args.train_data, TRAIN_SHA)
    evaluation, eval_sha = load_pinned(args.eval_data, EVAL_SHA)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer_dir), use_fast=True, local_files_only=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": SOURCE_RUN_ID,
        "train_sha256": train_sha,
        "eval_sha256": eval_sha,
        "audit": "exact training encode_record EOS/label placement",
        "device": "cpu", "gpu_training_performed": False,
        "raw_text_exported": False, "quality_certified": False,
        "promotion_approved": False,
        "train": audit_rows(train, tokenizer, args.max_length),
        "eval": audit_rows(evaluation, tokenizer, args.max_length),
        "limitations": "EOS placement audit only; cannot establish semantic answer quality or root cause of early EOS.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Completed pinned CPU EOS label audit; aggregate-only report; no model promotion")


if __name__ == "__main__":
    main()
