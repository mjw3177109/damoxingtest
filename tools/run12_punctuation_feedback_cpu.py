#!/usr/bin/env python3
"""Bounded CPU audit of punctuation feedback in rejected Run 12 (no training)."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from first_token_probability_probe import apply_repetition_penalty
from generation_decode_probe import read_prompts
from run12_direct_answer_generation import verify_adapter
from run12_first_step_category_cpu import category_ids, measure_categories
from run12_token_type_parity import make_inputs
from run12_tokenized_direct_answer_audit import (
    ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION,
)

PHASES = ("base", "candidate")
PROMPT_COUNT = 4
FORCED_COUNTS = (0, 1, 2, 3)
PENALTY = 1.12


def summarize(rows):
    expected = {(phase, i, count) for phase in PHASES
                for i in range(PROMPT_COUNT) for count in FORCED_COUNTS}
    keys = [(r["phase"], r["prompt_index"], r["forced_punctuation_count"]) for r in rows]
    if len(keys) != len(expected) or set(keys) != expected or len(set(keys)) != len(keys):
        raise ValueError("Expected 32 unique CPU observations")
    by_key = dict(zip(keys, rows))
    pairs = []
    for i in range(PROMPT_COUNT):
        for count in FORCED_COUNTS:
            base = by_key["base", i, count]
            candidate = by_key["candidate", i, count]
            if base["history_sha256"] != candidate["history_sha256"]:
                raise ValueError("Unmatched fixed-token histories")
            for row in (base, candidate):
                for key in ("punctuation_probability", "unk_probability", "eos_probability"):
                    value = row["processed"][key]
                    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                        raise ValueError("Invalid probability")
            pairs.append({
                "prompt_index": i, "forced_punctuation_count": count,
                "base_punctuation_top1": base["processed"]["top1_category"] == "punctuation",
                "candidate_punctuation_top1": candidate["processed"]["top1_category"] == "punctuation",
                "candidate_minus_base_punctuation_probability": round(
                    candidate["processed"]["punctuation_probability"]
                    - base["processed"]["punctuation_probability"], 9),
            })
    return {
        "matched_pairs": len(pairs),
        "punctuation_top1_by_forced_count": {
            phase: {str(count): sum(by_key[phase, i, count]["processed"]["top1_category"] == "punctuation"
                                    for i in range(PROMPT_COUNT))
                    for count in FORCED_COUNTS}
            for phase in PHASES},
        "candidate_minus_base_mean_punctuation_probability_by_forced_count": {
            str(count): round(sum(p["candidate_minus_base_punctuation_probability"]
                                  for p in pairs if p["forced_punctuation_count"] == count) / PROMPT_COUNT, 9)
            for count in FORCED_COUNTS},
        "pairs": pairs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verify_adapter(args.adapter)
    prompts, eval_hash = read_prompts(args.eval_data, EVAL_SHA256, limit=PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        parser.error("Four pinned prompts required")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.cuda.is_available():
        parser.error("CPU-only audit; CUDA is visible")
    torch.manual_seed(42)
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REVISION).cpu().eval()
    vocab = base.get_input_embeddings().num_embeddings
    if vocab != len(tokenizer):
        parser.error("Tokenizer/model vocabulary mismatch")
    categories = category_ids(tokenizer, vocab)
    period_ids = tokenizer.encode(".", add_special_tokens=False)
    if len(period_ids) != 1 or period_ids[0] not in categories["punctuation"]:
        parser.error("Period is not a single punctuation token")
    period_id = period_ids[0]
    rows = []

    def audit(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            prompt_ids = make_inputs(tokenizer, prompt, "train_parity")["input_ids"][0].tolist()
            if len(prompt_ids) + max(FORCED_COUNTS) >= model.config.n_positions:
                raise ValueError("Context length exceeded")
            for count in FORCED_COUNTS:
                history = prompt_ids + [period_id] * count
                with torch.inference_mode():
                    logits = model(input_ids=torch.tensor([history], dtype=torch.long),
                                   attention_mask=torch.ones((1, len(history)), dtype=torch.long),
                                   use_cache=False).logits[0, -1].float().cpu().tolist()
                processed = apply_repetition_penalty(logits, history, PENALTY)
                rows.append({
                    "phase": phase, "prompt_index": index,
                    "forced_punctuation_count": count,
                    "history_sha256": hashlib.sha256(json.dumps(history).encode("ascii")).hexdigest(),
                    "raw": measure_categories(logits, categories),
                    "processed": measure_categories(processed, categories),
                })

    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "source_training_run_id": 39921870784,
        "source_first_step_audit_run_id": 40092707377,
        "model": MODEL, "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": eval_hash,
        "device": "cpu", "forward_passes": len(rows),
        "forced_punctuation_counts": list(FORCED_COUNTS),
        "repetition_penalty": PENALTY,
        "summary": summarize(rows), "rows": rows,
        "new_gpu_training": False, "new_model_answers": False,
        "promotion_approved": False,
        "limitations": "Four fixed prompts and forced periods, not free generation or causal proof. No model promotion.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: 32 bounded CPU forwards, 16 matched pairs; no training or promotion")


if __name__ == "__main__":
    main()
