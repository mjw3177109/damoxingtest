#!/usr/bin/env python3
"""Bounded CPU-only period-token probability/rank audit for rejected Run 12."""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from first_token_probability_probe import apply_repetition_penalty
from generation_decode_probe import read_prompts
from run12_direct_answer_generation import verify_adapter
from run12_punctuation_feedback_cpu import FORCED_COUNTS, PENALTY, PHASES, PROMPT_COUNT
from run12_token_type_parity import make_inputs
from run12_tokenized_direct_answer_audit import ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION


def measure_token(logits, period_id, unk_id, eos_id):
    """Stable probabilities and deterministic ranks, without exposing token IDs."""
    values = [float(v) for v in logits]
    ids = (period_id, unk_id, eos_id)
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("Invalid logits")
    if any(type(i) is not int or not 0 <= i < len(values) for i in ids) or len(set(ids)) != 3:
        raise ValueError("Invalid or overlapping watched tokens")
    peak = max(values)
    weights = [math.exp(v - peak) for v in values]
    denominator = sum(weights)
    result = {}
    for name, token_id in zip(("period", "unk", "eos"), ids):
        score = values[token_id]
        rank = 1 + sum(v > score or (v == score and i < token_id) for i, v in enumerate(values))
        result[name + "_probability"] = round(weights[token_id] / denominator, 9)
        result[name + "_rank"] = rank
    result["period_top1"] = result["period_rank"] == 1
    return result


def summarize(rows):
    expected = {(phase, i, count) for phase in PHASES
                for i in range(PROMPT_COUNT) for count in FORCED_COUNTS}
    keys = [(r["phase"], r["prompt_index"], r["forced_period_count"]) for r in rows]
    if len(keys) != len(expected) or set(keys) != expected or len(set(keys)) != len(keys):
        raise ValueError("Expected exactly 32 unique observations")
    lookup = dict(zip(keys, rows))
    pairs = []
    for index in range(PROMPT_COUNT):
        for count in FORCED_COUNTS:
            base = lookup["base", index, count]
            candidate = lookup["candidate", index, count]
            if base["history_sha256"] != candidate["history_sha256"]:
                raise ValueError("Mismatched input histories")
            for row in (base, candidate):
                for measurement in ("raw", "processed"):
                    scores = row[measurement]
                    for name in ("period", "unk", "eos"):
                        prob = scores[name + "_probability"]
                        rank = scores[name + "_rank"]
                        if type(prob) not in (int, float) or not math.isfinite(prob) or not 0 <= prob <= 1:
                            raise ValueError("Invalid probability")
                        if type(rank) is not int or rank < 1:
                            raise ValueError("Invalid rank")
                    if type(scores["period_top1"]) is not bool or scores["period_top1"] != (scores["period_rank"] == 1):
                        raise ValueError("Inconsistent period Top1")
                    if sum(scores[n + "_probability"] for n in ("period", "unk", "eos")) > 1.00000001:
                        raise ValueError("Probabilities exceed one")
            pairs.append({
                "prompt_index": index, "forced_period_count": count,
                "base_period_top1": base["processed"]["period_top1"],
                "candidate_period_top1": candidate["processed"]["period_top1"],
                "base_period_rank": base["processed"]["period_rank"],
                "candidate_period_rank": candidate["processed"]["period_rank"],
                "candidate_minus_base_period_probability": round(
                    candidate["processed"]["period_probability"] - base["processed"]["period_probability"], 9),
            })
    return {
        "matched_pairs": len(pairs),
        "period_top1_by_forced_count": {
            phase: {str(count): sum(lookup[phase, i, count]["processed"]["period_top1"]
                                    for i in range(PROMPT_COUNT)) for count in FORCED_COUNTS}
            for phase in PHASES},
        "mean_period_probability_by_forced_count": {
            phase: {str(count): round(sum(lookup[phase, i, count]["processed"]["period_probability"]
                                          for i in range(PROMPT_COUNT)) / PROMPT_COUNT, 9)
                    for count in FORCED_COUNTS}
            for phase in PHASES},
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
        parser.error("Exactly four pinned prompts required")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.cuda.is_available():
        parser.error("CPU-only: CUDA must be invisible")
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
    period_ids = tokenizer.encode(".", add_special_tokens=False)
    if len(period_ids) != 1 or period_ids[0] in (tokenizer.unk_token_id, tokenizer.eos_token_id):
        parser.error("Period must be one non-special token")
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
                    "phase": phase, "prompt_index": index, "forced_period_count": count,
                    "history_sha256": hashlib.sha256(json.dumps(history).encode("ascii")).hexdigest(),
                    "raw": measure_token(logits, period_id, tokenizer.unk_token_id, tokenizer.eos_token_id),
                    "processed": measure_token(processed, period_id, tokenizer.unk_token_id, tokenizer.eos_token_id),
                })

    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "source_training_run_id": 39921870784,
        "source_category_audit_run_id": 40100735421,
        "model": MODEL, "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": eval_hash,
        "device": "cpu", "forward_passes": len(rows),
        "forced_period_counts": list(FORCED_COUNTS), "repetition_penalty": PENALTY,
        "summary": summarize(rows), "rows": rows,
        "new_gpu_training": False, "new_model_answers": False,
        "promotion_approved": False,
        "limitations": "Four fixed prompts and forced periods; single-token ranks are not free-generation evidence or proof of root cause.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: 32 bounded CPU forwards, 16 matched histories; no training or promotion")


if __name__ == "__main__":
    main()
