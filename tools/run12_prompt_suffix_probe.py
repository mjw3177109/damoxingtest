#!/usr/bin/env python3
"""Bounded CPU-only prompt-suffix sensitivity probe; no training or promotion.

The production training and generation prefixes already match. This probe
tests ONE hypothetical suffix change, not a known training bug.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION,
    analyze_tokens, read_prompts,
)
from run12_readability_review import safe_excerpt, diagnose_decode_visibility
from run12_unk_fixed_prefix_probe import ADAPTER_SHA, measure_unk

SETTINGS = ("train_parity", "assistant_newline")
PHASES = ("base", "candidate")
PROMPT_COUNT = 4
MAX_NEW_TOKENS = 64


def variant_prompt(prompt, setting):
    if not isinstance(prompt, str) or not prompt.endswith("\n助手："):
        raise ValueError("Prompt does not match the production training prefix")
    if setting == "train_parity":
        return prompt
    if setting == "assistant_newline":
        return prompt + "\n"
    raise ValueError("Unknown setting")


def verify_production_parity(path):
    """Fail closed if the training and generation template contract changes."""
    source = Path(path).read_text(encoding="utf-8")
    train = 'prefix = "用户：" + record["instruction"] + "\\n助手："'
    infer = 'prompts = ["用户：" + item["instruction"] + "\\n助手："'
    if train not in source or infer not in source:
        raise ValueError("Production training/generation template parity not established")
    return True


def summarize(rows):
    expected = {(p, s, i) for p in PHASES for s in SETTINGS for i in range(PROMPT_COUNT)}
    keys = [(r["phase"], r["setting"], r["prompt_index"]) for r in rows]
    if len(keys) != len(expected) or len(set(keys)) != len(expected) or set(keys) != expected:
        raise ValueError("Expected 16 unique phase/template/prompt observations")
    result = {}
    for phase in PHASES:
        controls = {r["prompt_index"]: r for r in rows
                    if r["phase"] == phase and r["setting"] == "train_parity"}
        for setting in SETTINGS:
            group = [r for r in rows if r["phase"] == phase and r["setting"] == setting]
            if any(r["instruction_sha256"] != controls[r["prompt_index"]]["instruction_sha256"]
                   for r in group):
                raise ValueError("Mismatched instruction between settings")
            result[phase + "/" + setting] = {
                "count": len(group),
                "punctuation_only": sum(bool(r["punctuation_only"]) for r in group),
                "contains_chinese": sum(bool(r["contains_chinese"]) for r in group),
                "eos": sum(r["stop_reason_inferred"] == "eos" for r in group),
                "max_token_limit": sum(r["stop_reason_inferred"] == "max_new_tokens" for r in group),
                "blank": sum(r["decode_visibility"]["stripped_decode_length"] == 0 for r in group),
                "unk_first_top1": sum(r["first_step_unk"]["processed"]["unk_rank"] == 1 for r in group),
                "mean_first_step_unk_probability": round(
                    sum(r["first_step_unk"]["processed"]["unk_probability"] for r in group) / len(group), 9),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--training-script", type=Path, default=Path("scripts/train_gpt2_lora.py"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    verify_production_parity(args.training_script)
    config = args.adapter / "adapter_config.json"
    weights = args.adapter / "adapter_model.safetensors"
    if not config.is_file() or not weights.is_file():
        parser.error("Exact rejected Run 12 Adapter required")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != ADAPTER_SHA:
        parser.error("Adapter SHA-256 mismatch")
    if json.loads(config.read_text(encoding="utf-8")).get("base_model_name_or_path") != DEFAULT_MODEL:
        parser.error("Base model mismatch")
    prompts, holdout_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, PROMPT_COUNT)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(2)
    torch.manual_seed(42)
    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.unk_token_id is None:
        raise RuntimeError("Tokenizer has no UNK token")
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise RuntimeError("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def evaluate(model, phase):
        model.eval()
        for index, original in enumerate(prompts):
            for setting in SETTINGS:
                prompt = variant_prompt(original, setting)
                encoded = dict(tokenizer(prompt, return_tensors="pt"))
                # Training uses input_ids and attention_mask, not token_type_ids.
                inputs = {key: encoded[key] for key in ("input_ids", "attention_mask")}
                history = inputs["input_ids"][0].tolist()
                with torch.inference_mode():
                    first_logits = model(**inputs, use_cache=False).logits[0, -1].float().tolist()
                first_unk = measure_unk(first_logits, history, tokenizer.unk_token_id)
                torch.manual_seed(42 + index)
                with torch.inference_mode():
                    generated = model.generate(
                        **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                        repetition_penalty=1.12,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                token_ids = generated[0][inputs["input_ids"].shape[1]:].tolist()
                diagnostics = analyze_tokens(token_ids, tokenizer, MAX_NEW_TOKENS, include_text=True)
                output = diagnostics.pop("output")
                diagnostics.pop("token_ids")
                rows.append({
                    "phase": phase,
                    "setting": setting,
                    "prompt_index": index,
                    "instruction_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                    "first_step_unk": first_unk,
                    "contains_chinese": any("\u3400" <= ch <= "\u9fff" for ch in output),
                    "safe_output_excerpt": safe_excerpt(output),
                    "decode_visibility": diagnose_decode_visibility(token_ids, tokenizer),
                    **diagnostics,
                })

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    evaluate(candidate, "candidate")
    summary = summarize(rows)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "train-parity assistant suffix vs same suffix plus newline; one variable only",
        "source_training_run_id": 39921870784,
        "model": DEFAULT_MODEL, "model_revision": DEFAULT_REVISION,
        "adapter_weights_sha256": ADAPTER_SHA,
        "holdout_sha256": holdout_sha, "device": "cpu", "seed": 42,
        "generation_settings": {"do_sample": False, "max_new_tokens": 64,
                                "repetition_penalty": 1.12, "token_type_ids": "excluded"},
        "production_training_and_generation_templates_already_match": True,
        "hypothetical_variant_only": True,
        "generations": len(rows), "first_token_forward_passes": len(rows),
        "summary": summary, "results": rows,
        "new_gpu_training": False, "promotion_approved": False,
        "quality_certified": False,
        "limitations": "Prompt sensitivity is not proof of training root cause; human review is still required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS:", len(rows), "bounded CPU generations; no GPU or promotion")


if __name__ == "__main__":
    main()
