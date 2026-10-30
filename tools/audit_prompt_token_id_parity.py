#!/usr/bin/env python3
"""Read-only Run 12 prompt token-ID parity audit; exports aggregate counts only.

Compares historical default tokenizer(prompt) with explicit add_special_tokens=False.
Does not train, generate text, access Kaggle, or export prompt/token IDs.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MODEL = "uer/gpt2-chinese-cluecorpussmall"
REVISION = "c2c0249d8a2731f269414cc3b22dff021f8e07a3"
EVAL_SHA256 = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"
EXPECTED_PROMPTS = 10


def load_prompts(path):
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != EVAL_SHA256:
        raise ValueError("Holdout SHA-256 mismatch; refusing cross-version comparison")
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    if len(rows) < EXPECTED_PROMPTS or not all(isinstance(x, dict) and isinstance(x.get("instruction"), str) for x in rows):
        raise ValueError("Invalid or incomplete fixed holdout")
    return ["用户：" + row["instruction"] + "\n助手：" for row in rows[:EXPECTED_PROMPTS]]


def compare_token_ids(tokenizer, prompts):
    if len(prompts) != EXPECTED_PROMPTS:
        raise ValueError("Expected exactly ten fixed prompts")
    results = []
    for index, prompt in enumerate(prompts):
        old_ids = tokenizer(prompt)["input_ids"]
        new_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        if not isinstance(old_ids, list) or not isinstance(new_ids, list):
            raise TypeError("Tokenizer must return unbatched integer ID lists")
        if not all(isinstance(v, int) for v in old_ids + new_ids):
            raise TypeError("Non-integer tokenizer output")
        results.append({
            "index": index,
            "default_length": len(old_ids),
            "explicit_false_length": len(new_ids),
            "token_ids_differ": old_ids != new_ids,
        })
    return {
        "prompt_count": len(results),
        "different_token_id_sequences": sum(r["token_ids_differ"] for r in results),
        "length_differences": sum(r["default_length"] != r["explicit_false_length"] for r in results),
        "per_prompt_aggregate": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", default="data/safety_humanity_eval_v1.jsonl")
    parser.add_argument("--output", default="token_id_parity.json")
    args = parser.parse_args()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, use_fast=True)
    if tokenizer.eos_token is None:
        if tokenizer.sep_token is not None:
            tokenizer.eos_token = tokenizer.sep_token
        else:
            tokenizer.add_special_tokens({"eos_token": "<|endoftext|>"})
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    comparison = compare_token_ids(tokenizer, load_prompts(args.eval))
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": 39921870784,
        "model": MODEL,
        "model_revision": REVISION,
        "holdout_sha256": EVAL_SHA256,
        "tokenizer_class": type(tokenizer).__name__,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
        "bos_token_id": tokenizer.bos_token_id,
        "add_bos_token": getattr(tokenizer, "add_bos_token", None),
        **comparison,
        "promotion_approved": False,
        "scope": "CPU tokenizer encoding only; no model forward or GPU training",
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"prompt_count": result["prompt_count"], "different_token_id_sequences": result["different_token_id_sequences"], "length_differences": result["length_differences"], "promotion_approved": False}))


if __name__ == "__main__":
    main()
