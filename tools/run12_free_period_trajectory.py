#!/usr/bin/env python3
"""CPU-only, bounded free-generation period-loop audit for rejected Run 12.

No training, model changes, raw prompts, decoded outputs, or token IDs are exported.
"""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import read_prompts
from run12_direct_answer_generation import verify_adapter
from run12_token_type_parity import make_inputs
from run12_tokenized_direct_answer_audit import ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION

PHASES = ("base", "candidate")
PROMPT_COUNT = 4
MAX_NEW_TOKENS = 32
PENALTY = 1.12


def longest_period_run(ids, period_id):
    current = best = 0
    for token in ids:
        current = current + 1 if token == period_id else 0
        best = max(best, current)
    return best


def describe_trajectory(ids, scores, period_id, unk_id, eos_id):
    """Summarize the actual greedy path; scores are HF processed next-token logits."""
    if not ids or len(ids) != len(scores) or len(ids) > MAX_NEW_TOKENS:
        raise ValueError("Invalid generated path/scores length")
    if len({period_id, unk_id, eos_id}) != 3:
        raise ValueError("Watched token IDs overlap")
    first = next((i for i, token in enumerate(ids) if token == period_id), None)
    after = first + 1 if first is not None and first + 1 < len(ids) else None
    next_probability = next_rank = None
    if after is not None:
        # Import only when real CPU inference is running.
        import torch
        row = scores[after][0].float().cpu()
        if not torch.isfinite(row).all():
            raise ValueError("Non-finite processed logits")
        next_probability = round(float(torch.softmax(row, dim=-1)[period_id]), 9)
        target = row[period_id]
        next_rank = 1 + int((row > target).sum()) + int(
            ((row == target) & (torch.arange(row.numel()) < period_id)).sum()
        )
    return {
        "generated_token_count": len(ids),
        "period_token_count": ids.count(period_id),
        "unk_token_count": ids.count(unk_id),
        "first_period_position": first,
        "first_period_followed_by_period": ids[after] == period_id if after is not None else None,
        "next_step_period_probability": next_probability,
        "next_step_period_rank": next_rank,
        "longest_period_run": longest_period_run(ids, period_id),
        "stop_reason": "eos" if eos_id in ids else (
            "max_new_tokens" if len(ids) == MAX_NEW_TOKENS else "other"
        ),
    }


def summarize(rows):
    expected = {(phase, i) for phase in PHASES for i in range(PROMPT_COUNT)}
    keys = [(row["phase"], row["prompt_index"]) for row in rows]
    if len(keys) != len(expected) or len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError("Expected exactly eight unique generations")
    by_key = dict(zip(keys, rows))
    for index in range(PROMPT_COUNT):
        if by_key["base", index]["input_history_sha256"] != by_key["candidate", index]["input_history_sha256"]:
            raise ValueError("Base/candidate inputs do not match")
    for row in rows:
        steps = row["generated_token_count"]
        count = row["period_token_count"]
        first = row["first_period_position"]
        streak = row["longest_period_run"]
        if type(steps) is not int or not 1 <= steps <= MAX_NEW_TOKENS:
            raise ValueError("Invalid generation length")
        if type(count) is not int or not 0 <= count <= steps:
            raise ValueError("Invalid period count")
        if type(streak) is not int or not 0 <= streak <= count:
            raise ValueError("Invalid period streak")
        if (first is None) != (count == 0) or (first is not None and
                                               (type(first) is not int or not 0 <= first < steps)):
            raise ValueError("Invalid first period position")
        if type(row["unk_token_count"]) is not int or not 0 <= row["unk_token_count"] <= steps:
            raise ValueError("Invalid UNK count")
        if row["stop_reason"] not in ("eos", "max_new_tokens", "other"):
            raise ValueError("Invalid stop reason")
        followed = row["first_period_followed_by_period"]
        probability = row["next_step_period_probability"]
        rank = row["next_step_period_rank"]
        has_next = first is not None and first + 1 < steps
        if has_next:
            if type(followed) is not bool or type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1 or type(rank) is not int or rank < 1:
                raise ValueError("Invalid post-period measurement")
        elif any(x is not None for x in (followed, probability, rank)):
            raise ValueError("Unexpected post-period measurement")
    return {
        phase: {
            "generations": PROMPT_COUNT,
            "period_seen": sum(r["first_period_position"] is not None for r in rows if r["phase"] == phase),
            "first_period_followed_by_period": sum(r["first_period_followed_by_period"] is True for r in rows if r["phase"] == phase),
            "max_token_limit": sum(r["stop_reason"] == "max_new_tokens" for r in rows if r["phase"] == phase),
            "total_period_tokens": sum(r["period_token_count"] for r in rows if r["phase"] == phase),
            "total_unk_tokens": sum(r["unk_token_count"] for r in rows if r["phase"] == phase),
            "max_period_streak": max(r["longest_period_run"] for r in rows if r["phase"] == phase),
        } for phase in PHASES
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify_adapter(args.adapter)
    prompts, holdout_sha = read_prompts(args.eval_data, EVAL_SHA256, limit=PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        parser.error("Exactly four fixed prompts required")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.cuda.is_available():
        parser.error("CUDA visible: CPU-only audit refuses to run")
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    period_ids = tokenizer.encode(".", add_special_tokens=False)
    if len(period_ids) != 1 or any(period_ids[0] == t for t in (tokenizer.unk_token_id, tokenizer.eos_token_id)):
        parser.error("Period must be exactly one non-special token")
    base = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        parser.error("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def audit(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = make_inputs(tokenizer, prompt, "train_parity")
            if inputs["input_ids"].shape[1] + MAX_NEW_TOKENS > model.config.n_positions:
                raise ValueError("Context window exceeded")
            history = inputs["input_ids"][0].tolist()
            torch.manual_seed(42 + index)
            with torch.inference_mode():
                output = model.generate(
                    **inputs, do_sample=False, max_new_tokens=MAX_NEW_TOKENS,
                    repetition_penalty=PENALTY, pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    return_dict_in_generate=True, output_scores=True,
                )
            generated = output.sequences[0][len(history):].tolist()
            rows.append({
                "phase": phase, "prompt_index": index,
                "input_history_sha256": hashlib.sha256(json.dumps(history).encode("ascii")).hexdigest(),
                **describe_trajectory(generated, output.scores, period_ids[0],
                                      tokenizer.unk_token_id, tokenizer.eos_token_id),
            })

    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "source_training_run_id": 39921870784,
        "source_period_audit_run_id": 40104958975,
        "model": MODEL, "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": holdout_sha,
        "device": "cpu", "generations": len(rows),
        "decoding": {"do_sample": False, "max_new_tokens": MAX_NEW_TOKENS,
                     "repetition_penalty": PENALTY, "seed_per_prompt": "42 + index"},
        "summary": summarize(rows), "rows": rows,
        "new_gpu_training": False, "new_model_answers": False, "promotion_approved": False,
        "limitations": "Four pinned prompts; greedy paths are diagnostic, not quality certification or causal proof. No raw tokens/text exported.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: eight bounded CPU greedy paths, four matched prompts, no training or promotion")


if __name__ == "__main__":
    main()
