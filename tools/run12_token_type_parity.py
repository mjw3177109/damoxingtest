#!/usr/bin/env python3
"""CPU-only Run 12 token_type_ids input-parity audit; no training or promotion."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION,
    analyze_tokens, read_prompts,
)


def make_inputs(tokenizer, prompt, setting):
    if setting not in ("original", "train_parity", "train_exact"):
        raise ValueError("Unknown setting")
    # Keep the historical token_type-only comparison unchanged.  A distinct
    # mode is needed for *actual* training parity, which also omits automatic
    # special tokens (see scripts/train_gpt2_lora.py).
    if setting == "train_exact":
        result = dict(tokenizer(prompt, add_special_tokens=False, return_tensors="pt"))
    else:
        result = dict(tokenizer(prompt, return_tensors="pt"))
    if "input_ids" not in result or "attention_mask" not in result:
        raise ValueError("Missing essential tokenizer tensors")
    if setting == "train_exact":
        result.pop("token_type_ids", None)
        return result
    if "token_type_ids" not in result:
        raise ValueError("Tokenizer did not return token_type_ids; no controlled difference")
    if result["token_type_ids"].shape != result["input_ids"].shape:
        raise ValueError("token_type_ids shape mismatch")
    if setting == "train_parity":
        result.pop("token_type_ids")
    return result


def summarize(rows):
    expected = {(phase, setting, index) for phase in ("base", "candidate")
                for setting in ("original", "train_parity") for index in range(10)}
    keys = [(r["phase"], r["setting"], r["prompt_index"]) for r in rows]
    if len(keys) != 40 or set(keys) != expected or len(set(keys)) != 40:
        raise ValueError("Expected exactly 40 unique paired generations")
    result = {}
    for phase in ("base", "candidate"):
        grouped = {setting: [r for r in rows if r["phase"] == phase and r["setting"] == setting]
                   for setting in ("original", "train_parity")}
        for setting, subset in grouped.items():
            result[phase + "/" + setting] = {
                "n": 10,
                "punctuation_only": sum(bool(r["punctuation_only"]) for r in subset),
                "eos": sum(r["stop_reason_inferred"] == "eos" for r in subset),
                "max_token_limit": sum(r["stop_reason_inferred"] == "max_new_tokens" for r in subset),
                "mean_longest_character_run": round(sum(r["longest_identical_character_run"] for r in subset) / 10, 2),
            }
        control = {r["prompt_index"]: r for r in grouped["original"]}
        result[phase + "/first_token_changed"] = sum(
            r["first_token_id"] != control[r["prompt_index"]]["first_token_id"]
            for r in grouped["train_parity"]
        )
    return result


def verify_historical_control(summary):
    if summary["base/original"]["punctuation_only"] != 7:
        raise ValueError("Base control differs from audited Run 39950178751")
    if summary["candidate/original"]["punctuation_only"] != 10:
        raise ValueError("Candidate control differs from audited Run 39950178751")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", default=Path("data/safety_humanity_eval_v1.jsonl"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not (args.adapter / "adapter_config.json").is_file():
        parser.error("Run 12 Adapter missing")
    prompts, holdout_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=10)
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(2)
    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise RuntimeError("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def evaluate(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            for setting in ("original", "train_parity"):
                inputs = make_inputs(tokenizer, prompt, setting)
                torch.manual_seed(42 + index)
                with torch.inference_mode():
                    output = model.generate(
                        **inputs, do_sample=False, max_new_tokens=64,
                        repetition_penalty=1.12,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                generated = output[0][inputs["input_ids"].shape[1]:].tolist()
                diagnostic = analyze_tokens(generated, tokenizer, 64, include_text=False)
                diagnostic.pop("token_ids")
                rows.append({
                    "phase": phase, "setting": setting, "prompt_index": index,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "first_token_id": generated[0] if generated else None,
                    **diagnostic,
                })

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    evaluate(candidate, "candidate")
    summary = summarize(rows)
    verify_historical_control(summary)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": 39921870784,
        "historical_control_run_id": 39950178751,
        "model_revision": DEFAULT_REVISION,
        "holdout_sha256": holdout_sha,
        "device": "cpu",
        "experiment": "same weights/prompts/greedy settings; only token_type_ids included vs removed",
        "generations": 40,
        "summary": summary,
        "results": rows,
        "promotion_approved": False,
        "gpu_training_performed": False,
        "interpretation": "Input parity diagnosis only; punctuation reduction is not proof of quality or safety.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
