#!/usr/bin/env python3
"""Run 12 controlled CPU-only teacher-forced token audit.

Both models see identical fixed prefixes. No training, text samples or promotion.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from conditional_token_probe import adjust_repetition, extend_token_types, token_probability

SOURCE_RUN = "39921870784"
EXPECTED_ADAPTER_SHA256 = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"
FORCED_TOKENS = (119, 8601)
WATCH_TOKEN = 119
PROMPT_COUNT = 4
STEPS = 8


def trace_fixed_prefix(prompt_ids, forced_token_id, forward_logits, steps=STEPS, penalty=1.12):
    """Teacher force one fixed token after each step, regardless of argmax."""
    if not prompt_ids or not isinstance(forced_token_id, int) or forced_token_id < 0:
        raise ValueError("Invalid prompt or forced token")
    if not 1 <= steps <= STEPS:
        raise ValueError("Steps must be 1..8")
    history = list(prompt_ids)
    rows = []
    for step in range(steps):
        raw = [float(x) for x in forward_logits(history)]
        if forced_token_id >= len(raw) or WATCH_TOKEN >= len(raw):
            raise ValueError("Token ID outside vocabulary")
        processed = adjust_repetition(raw, history, penalty)
        top1 = max(range(len(processed)), key=lambda i: processed[i])
        rows.append({
            "step": step + 1,
            "forced_history_length": step,
            "raw_token119_probability": round(token_probability(raw, WATCH_TOKEN), 9),
            "processed_token119_probability": round(token_probability(processed, WATCH_TOKEN), 9),
            "processed_token119_rank": 1 + sum(v > processed[WATCH_TOKEN] for v in processed),
            "processed_top1_id": top1,
            "token119_is_top1": top1 == WATCH_TOKEN,
        })
        history.append(forced_token_id)
    return rows


def summarize(results):
    """Reject unmatched conditions; compare only same prompt and forced history."""
    if len(results) != PROMPT_COUNT * len(FORCED_TOKENS) * 2:
        raise ValueError("Expected 4 prompts x 2 forced prefixes x 2 models")
    by_key = {}
    for result in results:
        key = (result["prompt_index"], result["forced_token_id"], result["phase"])
        if key in by_key or key[0] not in range(PROMPT_COUNT) or key[1] not in FORCED_TOKENS or key[2] not in ("base", "candidate"):
            raise ValueError("Duplicate or unexpected result")
        if len(result["rows"]) != STEPS:
            raise ValueError("Incomplete trace")
        by_key[key] = result
    summaries = []
    for forced in FORCED_TOKENS:
        deltas = []
        base_top1 = candidate_top1 = 0
        for index in range(PROMPT_COUNT):
            base = by_key[index, forced, "base"]
            candidate = by_key[index, forced, "candidate"]
            if base["prompt_sha256"] != candidate["prompt_sha256"]:
                raise ValueError("Different prompts in comparison")
            for step, (b, c) in enumerate(zip(base["rows"], candidate["rows"]), 1):
                if b["step"] != step or c["step"] != step or b["forced_history_length"] != step - 1 or c["forced_history_length"] != step - 1:
                    raise ValueError("Mismatched teacher-forced history")
                for row in (b, c):
                    p = row["processed_token119_probability"]
                    if not isinstance(p, (float, int)) or not math.isfinite(p) or not 0 <= p <= 1:
                        raise ValueError("Invalid probability")
                deltas.append(c["processed_token119_probability"] - b["processed_token119_probability"])
                base_top1 += bool(b["token119_is_top1"])
                candidate_top1 += bool(c["token119_is_top1"])
        summaries.append({
            "forced_token_id": forced,
            "matched_history_pairs": len(deltas),
            "candidate_higher_token119_probability": sum(d > 0 for d in deltas),
            "candidate_lower_token119_probability": sum(d < 0 for d in deltas),
            "candidate_equal_token119_probability": sum(d == 0 for d in deltas),
            "mean_candidate_minus_base_token119_probability": round(sum(deltas) / len(deltas), 9),
            "base_token119_top1_steps": base_top1,
            "candidate_token119_top1_steps": candidate_top1,
        })
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from generation_decode_probe import DEFAULT_MODEL, DEFAULT_REVISION, DEFAULT_EVAL_SHA256, read_prompts
    adapter_config = args.adapter / "adapter_config.json"
    adapter_weights = args.adapter / "adapter_model.safetensors"
    if not adapter_config.is_file() or not adapter_weights.is_file():
        parser.error("Missing exact rejected Run 12 adapter")
    if hashlib.sha256(adapter_weights.read_bytes()).hexdigest() != EXPECTED_ADAPTER_SHA256:
        parser.error("Rejected Run 12 adapter hash mismatch")
    if json.loads(adapter_config.read_text(encoding="utf-8")).get("base_model_name_or_path") != DEFAULT_MODEL:
        parser.error("Unexpected base model")
    prompts, holdout_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        raise ValueError("Expected four fixed prompts")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(42)
    torch.set_num_threads(2)
    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION)
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    if max(FORCED_TOKENS) >= len(tokenizer):
        raise ValueError("Forced token outside tokenizer vocabulary")
    base.eval()
    results = []

    def measure(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            encoded = tokenizer(prompt, return_tensors="pt")
            prompt_ids = encoded["input_ids"][0].tolist()
            token_types = encoded["token_type_ids"][0].tolist() if "token_type_ids" in encoded else None
            if len(prompt_ids) + STEPS > model.config.n_positions:
                raise ValueError("Context window exceeded")
            def forward(history):
                kwargs = {
                    "input_ids": torch.tensor([history], dtype=torch.long),
                    "attention_mask": torch.ones((1, len(history)), dtype=torch.long),
                    "use_cache": False,
                }
                extended = extend_token_types(token_types, len(history))
                if extended is not None:
                    kwargs["token_type_ids"] = torch.tensor([extended], dtype=torch.long)
                with torch.inference_mode():
                    return model(**kwargs).logits[0, -1].float().tolist()
            for forced in FORCED_TOKENS:
                results.append({
                    "phase": phase,
                    "prompt_index": index,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "forced_token_id": forced,
                    "rows": trace_fixed_prefix(prompt_ids, forced, forward),
                })

    measure(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    measure(candidate, "candidate")

    # Exact first-step parity with the previously validated Run 39975111441.
    expected = {"base": [119, 8601, 119, 8601], "candidate": [119, 119, 119, 119]}
    for phase, expected_ids in expected.items():
        actual = [next(r for r in results if r["phase"] == phase and r["prompt_index"] == i and r["forced_token_id"] == 119)["rows"][0]["processed_top1_id"] for i in range(PROMPT_COUNT)]
        if actual != expected_ids:
            raise RuntimeError(f"Historical first-step parity mismatch: {phase} {actual}")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_type": "controlled_teacher_forced_same_prefix",
        "source_training_run_id": SOURCE_RUN,
        "model": DEFAULT_MODEL,
        "model_revision": DEFAULT_REVISION,
        "adapter_weights_sha256": EXPECTED_ADAPTER_SHA256,
        "holdout_sha256": holdout_sha,
        "device": "cpu",
        "forced_tokens": list(FORCED_TOKENS),
        "prompt_count": PROMPT_COUNT,
        "steps_per_trace": STEPS,
        "model_forward_passes": len(results) * STEPS,
        "first_step_parity": "matched audited Run 39975111441 for both models on all four prompts",
        "decode_processing": "repetition_penalty=1.12; complete attention_mask/token_type_ids; no sampling",
        "summary": summarize(results),
        "results": results,
        "new_gpu_training": False,
        "new_model_answers": False,
        "model_promotion_approved": False,
        "limitations": "Forced histories are diagnostic interventions, not model-generated answers. Changes in token probabilities alone do not establish root cause, quality, safety, or model improvement.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", report["model_forward_passes"], "CPU-only teacher-forced forward passes")


if __name__ == "__main__":
    main()
