#!/usr/bin/env python3
"""Audit one pre-registered token-changing prompt variant on rejected Run 12.

Tokenizer-only CPU diagnostic: no generation, training, checkpoint writes, or raw
prompts/token IDs in exported evidence. A changed tokenization is not a quality gain.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

MODEL = "uer/gpt2-chinese-cluecorpussmall"
MODEL_REVISION = "c2c0249d8a2731f269414cc3b22dff021f8e07a3"
EVAL_SHA256 = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"
ADAPTER_SHA256 = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"
PROMPT_COUNT = 4
VARIANT_DIRECTIVE = "请直接回答，不要复述问题。"


def token_digest(ids):
    if not ids or any(type(value) is not int or value < 0 for value in ids):
        raise ValueError("Nonempty nonnegative token IDs required")
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode("ascii")).hexdigest()


def variant_prompt(control):
    suffix = "\n助手："
    if not isinstance(control, str) or not control.startswith("用户：") or not control.endswith(suffix):
        raise ValueError("Unexpected fixed production prompt template")
    # One pre-registered variable: a direct-answer directive in the user turn.
    return control[:-len(suffix)] + "\n" + VARIANT_DIRECTIVE + suffix


def compare_prompt(control, tokenizer):
    variant = variant_prompt(control)
    control_ids = list(tokenizer(control, add_special_tokens=True)["input_ids"])
    variant_ids = list(tokenizer(variant, add_special_tokens=True)["input_ids"])
    first_diff = next((i for i, (a, b) in enumerate(zip(control_ids, variant_ids)) if a != b),
                      min(len(control_ids), len(variant_ids)))
    return {
        "token_sequence_changed": control_ids != variant_ids,
        "control_token_count": len(control_ids),
        "variant_token_count": len(variant_ids),
        "control_token_sha256": token_digest(control_ids),
        "variant_token_sha256": token_digest(variant_ids),
        "first_differing_position": None if control_ids == variant_ids else first_diff,
    }


def audit_records(records, tokenizer):
    if len(records) < PROMPT_COUNT:
        raise ValueError("Fixed holdout has fewer than four records")
    rows = []
    for index, record in enumerate(records[:PROMPT_COUNT]):
        if not isinstance(record, dict) or not isinstance(record.get("instruction"), str) or not record["instruction"].strip():
            raise ValueError("Invalid holdout instruction")
        control = "用户：" + record["instruction"] + "\n助手："
        rows.append({"prompt_index": index, **compare_prompt(control, tokenizer)})
    changed = sum(row["token_sequence_changed"] for row in rows)
    return {"count": len(rows), "changed_tokenizations": changed,
            "unchanged_tokenizations": len(rows) - changed, "results": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.eval_data.read_bytes()).hexdigest() != EVAL_SHA256:
        parser.error("Fixed holdout SHA-256 mismatch")
    weights = args.adapter / "adapter_model.safetensors"
    config = args.adapter / "adapter_config.json"
    tokenizer_config = args.adapter / "tokenizer_config.json"
    if not all(path.is_file() for path in (weights, config, tokenizer_config)):
        parser.error("Exact rejected adapter and tokenizer required; no fallback")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != ADAPTER_SHA256:
        parser.error("Rejected adapter SHA-256 mismatch")
    if json.loads(config.read_text(encoding="utf-8")).get("base_model_name_or_path") != MODEL:
        parser.error("Unexpected base model")
    records = [json.loads(line) for line in args.eval_data.read_text(encoding="utf-8").splitlines() if line.strip()]
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    result = audit_records(records, tokenizer)
    if result["changed_tokenizations"] != PROMPT_COUNT:
        parser.error("Pre-registered variant failed to change all four token sequences")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_training_run_id": 39921870784,
        "source_training_quality_gate": "rejected",
        "source_previous_cpu_run_id": 40076337028,
        "model": MODEL, "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": EVAL_SHA256,
        "variant": "insert one direct-answer directive before the assistant delimiter",
        "tokenizer_source": "exact_rejected_run12_adapter",
        "tokenizer_add_special_tokens": True,
        "device": "cpu", "model_forward_passes": 0,
        "new_gpu_training": False, "new_model_samples": False,
        "promotion_approved": False, "quality_certified": False,
        **result,
        "interpretation": "Tokenization changed; no model quality improvement is claimed. Next: bounded paired CPU generation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: fixed holdout 4/4 token sequences changed; no generation or training")


if __name__ == "__main__":
    main()
