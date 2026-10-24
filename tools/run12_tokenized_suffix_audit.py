#!/usr/bin/env python3
"""CPU-only tokenization parity audit for the rejected Run 12 prompt-suffix experiment.

No model forward pass, training, raw prompt text, or token IDs are exported.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MODEL = "uer/gpt2-chinese-cluecorpussmall"
MODEL_REVISION = "c2c0249d8a2731f269414cc3b22dff021f8e07a3"
EVAL_SHA256 = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"
ADAPTER_SHA256 = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"
PROMPT_COUNT = 4


def digest_ids(ids):
    if not ids or any(not isinstance(value, int) or value < 0 for value in ids):
        raise ValueError("Expected nonempty nonnegative token ID sequence")
    encoded = json.dumps(ids, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def compare_prompt(prompt, tokenizer):
    if not isinstance(prompt, str) or not prompt.endswith("\n助手："):
        raise ValueError("Unexpected production prompt template")
    # Match the generation-time tokenizer default: special tokens are enabled.
    control = list(tokenizer(prompt, add_special_tokens=True)["input_ids"])
    variant = list(tokenizer(prompt + "\n", add_special_tokens=True)["input_ids"])
    first_diff = next((i for i, (a, b) in enumerate(zip(control, variant))
                       if a != b), min(len(control), len(variant)))
    identical = control == variant
    return {
        "same_input_ids": identical,
        "control_token_count": len(control),
        "newline_token_count": len(variant),
        "control_token_sha256": digest_ids(control),
        "newline_token_sha256": digest_ids(variant),
        "first_differing_position": None if identical else first_diff,
    }


def audit_records(records, tokenizer):
    if len(records) < PROMPT_COUNT:
        raise ValueError("Not enough fixed holdout records")
    results = []
    for index, record in enumerate(records[:PROMPT_COUNT]):
        if not isinstance(record, dict) or not isinstance(record.get("instruction"), str):
            raise ValueError("Invalid holdout instruction")
        prompt = "用户：" + record["instruction"] + "\n助手："
        results.append({"prompt_index": index, **compare_prompt(prompt, tokenizer)})
    return {
        "count": len(results),
        "identical_tokenizations": sum(row["same_input_ids"] for row in results),
        "different_tokenizations": sum(not row["same_input_ids"] for row in results),
        "results": results,
    }


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
    if not weights.is_file() or not config.is_file():
        parser.error("Exact rejected Run 12 adapter files are required")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != ADAPTER_SHA256:
        parser.error("Rejected adapter weights SHA-256 mismatch")
    if json.loads(config.read_text(encoding="utf-8")).get("base_model_name_or_path") != MODEL:
        parser.error("Unexpected adapter base model")
    records = [json.loads(line) for line in args.eval_data.read_text(encoding="utf-8").splitlines()
               if line.strip()]

    from transformers import AutoTokenizer
    tokenizer_is_adapter = (args.adapter / "tokenizer_config.json").is_file()
    source = str(args.adapter) if tokenizer_is_adapter else MODEL
    kwargs = {"use_fast": True}
    if not tokenizer_is_adapter:
        kwargs["revision"] = MODEL_REVISION
    tokenizer = AutoTokenizer.from_pretrained(source, **kwargs)
    result = audit_records(records, tokenizer)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": 39921870784,
        "source_cpu_experiment_run_id": 40064518326,
        "model": MODEL,
        "model_revision": MODEL_REVISION,
        "adapter_weights_sha256": ADAPTER_SHA256,
        "holdout_sha256": EVAL_SHA256,
        "tokenizer_source": "rejected_run12_adapter" if tokenizer_is_adapter else "pinned_base_model_fallback",
        "experiment": "original production prompt vs same prompt plus one trailing newline",
        "tokenizer_add_special_tokens": True,
        "device": "cpu",
        "model_forward_passes": 0,
        "new_gpu_training": False,
        "promotion_approved": False,
        "quality_certified": False,
        **result,
        "interpretation": "Token parity only; does not establish language-model quality or training root cause.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: tokenized", result["count"], "fixed prompts; identical",
          result["identical_tokenizations"], "different", result["different_tokenizations"])


if __name__ == "__main__":
    main()
