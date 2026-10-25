#!/usr/bin/env python3
"""Read-only, aggregate-only audit of Run 12 GPT-2 response/EOS tokenization.

No raw instruction/response is written to the output. Does not load a model,
train, modify datasets, or access Kaggle credentials.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "uer/gpt2-chinese-cluecorpussmall"
RUN12_REVISION = "c2c0249d8a2731f269414cc3b22dff021f8e07a3"
RUN12_TRAIN_SHA = "ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c"
RUN12_EVAL_SHA = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"


def read_jsonl(path, expected_sha):
    content = Path(path).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_sha:
        raise ValueError(f"Dataset SHA-256 mismatch for {Path(path).name}; refusing to compare against Run 12")
    records = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
    if not records or not all(isinstance(x, dict) and isinstance(x.get("instruction"), str) and isinstance(x.get("response"), str) for x in records):
        raise ValueError("Invalid or empty instruction/response JSONL")
    return records, digest


def audit_records(tokenizer, records, max_length):
    """Mirror train_gpt2_lora.py encode_record exactly, without returning text."""
    if max_length < 1 or tokenizer.eos_token is None or tokenizer.eos_token_id is None:
        raise ValueError("Invalid max_length or missing EOS token")
    unk_token_id = getattr(tokenizer, "unk_token_id", None)
    rows = []
    for index, item in enumerate(records):
        prefix = "用户：" + item["instruction"] + "\n助手："
        answer = item["response"] + str(tokenizer.eos_token)
        prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
        full = prefix_ids + answer_ids
        truncated = full[:max_length]
        labels = ([-100] * len(prefix_ids) + answer_ids)[:max_length]
        supervised = [x for x in labels if x != -100]
        rows.append({
            "row_index": index, "prefix_tokens": len(prefix_ids), "answer_tokens": len(answer_ids),
            "full_tokens": len(full), "retained_tokens": len(truncated),
            "supervised_tokens": len(supervised), "was_truncated": len(full) > max_length,
            "eos_in_full": tokenizer.eos_token_id in answer_ids,
            "eos_at_full_end": bool(answer_ids and answer_ids[-1] == tokenizer.eos_token_id),
            "eos_in_supervised": tokenizer.eos_token_id in supervised,
            "eos_at_supervised_end": bool(supervised and supervised[-1] == tokenizer.eos_token_id),
            "zero_supervision": not supervised,
            "prefix_unk_tokens": sum(t == unk_token_id for t in prefix_ids) if unk_token_id is not None else None,
            "answer_unk_tokens": sum(t == unk_token_id for t in answer_ids) if unk_token_id is not None else None,
            "supervised_unk_tokens": sum(t == unk_token_id for t in supervised) if unk_token_id is not None else None,
        })
    return rows


def summarize(rows):
    def counts(key):
        return sum(bool(x[key]) for x in rows)
    def bounds(key):
        vals = sorted(x[key] for x in rows)
        return {"min": vals[0], "median": vals[len(vals)//2], "max": vals[-1]}
    def unk_summary(count_key, length_key):
        counts = [row[count_key] for row in rows]
        if any(count is None for count in counts):
            return {"count": None, "total_tokens": None, "percent": None}
        count = sum(counts)
        total = sum(row[length_key] for row in rows)
        return {"count": count, "total_tokens": total,
                "percent": round(100 * count / total, 4) if total else None}
    return {
        "records": len(rows),
        "prefix_tokens": bounds("prefix_tokens"),
        "answer_tokens": bounds("answer_tokens"),
        "full_tokens": bounds("full_tokens"),
        "supervised_tokens": bounds("supervised_tokens"),
        "truncated_records": counts("was_truncated"),
        "zero_supervision_records": counts("zero_supervision"),
        "unk_prefix": unk_summary("prefix_unk_tokens", "prefix_tokens"),
        "unk_answer": unk_summary("answer_unk_tokens", "answer_tokens"),
        "unk_supervised": unk_summary("supervised_unk_tokens", "supervised_tokens"),
        "eos_missing_from_full_answer": len(rows) - counts("eos_in_full"),
        "eos_not_at_full_answer_end": len(rows) - counts("eos_at_full_end"),
        "eos_missing_from_supervision": len(rows) - counts("eos_in_supervised"),
        "eos_not_at_supervised_end": len(rows) - counts("eos_at_supervised_end"),
        "truncated_row_indices": [x["row_index"] for x in rows if x["was_truncated"]],
        "eos_missing_row_indices": [x["row_index"] for x in rows if not x["eos_at_supervised_end"]],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", default="data/safety_humanity_train_v2.jsonl")
    parser.add_argument("--eval", default="data/safety_humanity_eval_v1.jsonl")
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--output", default="tokenizer_contract_audit.json")
    args = parser.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(DEFAULT_MODEL, revision=RUN12_REVISION, use_fast=True)
    if tokenizer.eos_token is None:
        if tokenizer.sep_token is not None:
            tokenizer.eos_token = tokenizer.sep_token
        else:
            tokenizer.add_special_tokens({"eos_token": "<|endoftext|>"})
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    datasets = (("train", args.train, RUN12_TRAIN_SHA), ("eval", args.eval, RUN12_EVAL_SHA))
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": 39921870784,
        "source_training_sha": "647b909a994441e3affa3f65fc46f9d0acb2c958",
        "model": DEFAULT_MODEL,
        "model_revision": RUN12_REVISION,
        "tokenizer_class": type(tokenizer).__name__,
        "tokenizer_eos_token_id": tokenizer.eos_token_id,
        "tokenizer_unk_token_id": tokenizer.unk_token_id,
        "tokenizer_sep_token_id": tokenizer.sep_token_id,
        "tokenizer_pad_token_id": tokenizer.pad_token_id,
        "tokenizer_vocab_size": len(tokenizer),
        "max_length": args.max_length,
        "datasets": {},
        "scope": "read-only real tokenizer / 109 source rows; aggregate counts only; no model forward or training",
        "promotion_approved": False,
    }
    for name, path, expected_sha in datasets:
        records, digest = read_jsonl(path, expected_sha)
        result["datasets"][name] = {"sha256": digest, **summarize(audit_records(tokenizer, records, args.max_length))}
    result["all_eos_supervised"] = all(v["eos_not_at_supervised_end"] == 0 for v in result["datasets"].values())
    result["all_untruncated"] = all(v["truncated_records"] == 0 for v in result["datasets"].values())
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_training_run_id": result["source_training_run_id"], "model_revision": RUN12_REVISION,
                      "train": result["datasets"]["train"], "eval": result["datasets"]["eval"],
                      "all_eos_supervised": result["all_eos_supervised"], "all_untruncated": result["all_untruncated"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
