#!/usr/bin/env python3
"""Bounded, CPU-only paired generation for a pre-audited Run 12 prompt variant.

Never trains, modifies weights, promotes a checkpoint, or exports raw token IDs.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import analyze_tokens, read_prompts
from run12_readability_review import diagnose_decode_visibility, safe_excerpt
from run12_token_type_parity import make_inputs
from run12_tokenized_direct_answer_audit import (
    ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION,
    PROMPT_COUNT, compare_prompt, variant_prompt,
)

MAX_NEW_TOKENS = 64
PHASES = ("base", "candidate")
SETTINGS = ("control", "direct_answer")


def verify_adapter(adapter):
    """Fail closed unless this is the exact previously rejected Run 12 adapter."""
    weights = adapter / "adapter_model.safetensors"
    config = adapter / "adapter_config.json"
    tokenizer = adapter / "tokenizer_config.json"
    if not all(path.is_file() for path in (weights, config, tokenizer)):
        raise ValueError("Exact rejected adapter/tokenizer files required")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != ADAPTER_SHA256:
        raise ValueError("Rejected adapter SHA-256 mismatch")
    if json.loads(config.read_text(encoding="utf-8")).get("base_model_name_or_path") != MODEL:
        raise ValueError("Unexpected adapter base model")


def summarize(rows):
    expected = {(p, s, i) for p in PHASES for s in SETTINGS for i in range(PROMPT_COUNT)}
    keys = [(r["phase"], r["setting"], r["prompt_index"]) for r in rows]
    if len(keys) != 16 or len(set(keys)) != 16 or set(keys) != expected:
        raise ValueError("Expected exactly 16 unique paired generations")
    summary = {}
    for phase in PHASES:
        for setting in SETTINGS:
            subset = [r for r in rows if r["phase"] == phase and r["setting"] == setting]
            summary[f"{phase}/{setting}"] = {
                "count": 4,
                "punctuation_only": sum(bool(r["punctuation_only"]) for r in subset),
                "blank_output": sum(bool(r["blank_output"]) for r in subset),
                "contains_chinese": sum(bool(r["contains_chinese"]) for r in subset),
                "eos": sum(r["stop_reason_inferred"] == "eos" for r in subset),
                "unk_only": sum(r["unk_token_count"] == r["generated_token_count"] and r["generated_token_count"] > 0 for r in subset),
                "mean_longest_identical_run": round(sum(r["longest_identical_character_run"] for r in subset) / 4, 2),
            }
    summary["control_matches_previous_cpu_review"] = (
        summary["base/control"]["punctuation_only"] == 0
        and summary["candidate/control"]["punctuation_only"] == 2
    )
    return summary


def build_row(phase, setting, index, prompt, token_ids, tokenizer):
    diagnostic = analyze_tokens(token_ids, tokenizer, MAX_NEW_TOKENS, include_text=True)
    raw_output = diagnostic.pop("output")
    diagnostic.pop("token_ids")
    visibility = diagnose_decode_visibility(token_ids, tokenizer)
    return {
        "phase": phase,
        "setting": setting,
        "prompt_index": index,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "safe_output_excerpt": safe_excerpt(raw_output),
        "contains_chinese": bool(re.search(r"[\u3400-\u9fff]", raw_output)),
        "blank_output": not bool(raw_output.strip()),
        "unk_token_count": visibility["special_token_categories"]["unk"],
        "decode_visibility": visibility,
        **diagnostic,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, EVAL_SHA256, limit=PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        parser.error("Exactly four fixed prompts required")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if torch.cuda.is_available():
        parser.error("CPU-only experiment: CUDA visible, refusing execution")
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if not all(compare_prompt(prompt, tokenizer)["token_sequence_changed"] for prompt in prompts):
        parser.error("Variant failed to change all four token sequences")
    base = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        parser.error("Tokenizer/base vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def evaluate(model, phase):
        model.eval()
        for index, control in enumerate(prompts):
            for setting in SETTINGS:
                prompt = control if setting == "control" else variant_prompt(control)
                inputs = make_inputs(tokenizer, prompt, "train_parity")
                torch.manual_seed(42 + index)
                with torch.inference_mode():
                    output = model.generate(
                        **inputs, do_sample=False, max_new_tokens=MAX_NEW_TOKENS,
                        repetition_penalty=1.12, pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                ids = output[0][inputs["input_ids"].shape[1]:].tolist()
                rows.append(build_row(phase, setting, index, prompt, ids, tokenizer))

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    evaluate(candidate, "candidate")
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_training_run_id": 39921870784,
        "source_previous_tokenization_run_id": 40084814850,
        "source_previous_readability_run_id": 40048108519,
        "model": MODEL, "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": eval_sha,
        "experiment": "control vs one direct-answer directive; base vs rejected Run 12 LoRA",
        "device": "cpu", "decoding": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS,
                                    "repetition_penalty": 1.12, "seed_per_prompt": "42 + index",
                                    "input_mode": "train_parity_without_token_type_ids"},
        "generations": len(rows), "summary": summarize(rows), "results": rows,
        "gpu_training_performed": False, "quality_certified": False,
        "promotion_approved": False,
        "limitations": "Four prompts, no automatic quality certification. Review excerpts manually; preserve negative results.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
