#!/usr/bin/env python3
"""Read-only CPU experiment: compare UNK probabilities on identical forced histories."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from generation_decode_probe import DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION, read_prompts
from first_token_probability_probe import apply_repetition_penalty

ADAPTER_SHA = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"
PROMPTS = 4
STEPS = 5


def measure_unk(logits, history, unk_id, penalty=1.12):
    raw = [float(v) for v in logits]
    if not raw or not all(math.isfinite(v) for v in raw):
        raise ValueError("Empty or non-finite logits")
    if not isinstance(unk_id, int) or not 0 <= unk_id < len(raw):
        raise ValueError("Invalid UNK token")
    if not history or any(not isinstance(x, int) or x < 0 or x >= len(raw) for x in history):
        raise ValueError("Invalid fixed history")
    processed = apply_repetition_penalty(raw, history, penalty)
    def stats(values):
        peak = max(values)
        logit = values[unk_id]
        denominator = sum(math.exp(v - peak) for v in values)
        return {
            "unk_logit": round(logit, 6),
            "unk_probability": round(math.exp(logit - peak) / denominator, 9),
            "unk_rank": 1 + sum(v > logit for v in values),
            "unk_margin_to_top1": round(logit - peak, 6),
            "unk_is_top1": logit == peak,
        }
    return {"raw": stats(raw), "processed": stats(processed)}


def compare_pairs(rows):
    expected = {(phase, i, step) for phase in ("base", "candidate")
                for i in range(PROMPTS) for step in range(STEPS)}
    keys = [(r["phase"], r["prompt_index"], r["forced_unk_count"]) for r in rows]
    if len(keys) != len(expected) or len(set(keys)) != len(expected) or set(keys) != expected:
        raise ValueError("Missing or duplicated fixed-prefix observations")
    lookup = {key: row for key, row in zip(keys, rows)}
    comparisons = []
    for i in range(PROMPTS):
        for step in range(STEPS):
            b = lookup["base", i, step]
            c = lookup["candidate", i, step]
            if b["prompt_sha256"] != c["prompt_sha256"]:
                raise ValueError("Mismatched prompt")
            bp = b["statistics"]["processed"]["unk_probability"]
            cp = c["statistics"]["processed"]["unk_probability"]
            if not all(isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1 for p in (bp, cp)):
                raise ValueError("Invalid probability")
            comparisons.append({
                "prompt_index": i,
                "forced_unk_count": step,
                "base_processed_unk_probability": bp,
                "candidate_processed_unk_probability": cp,
                "candidate_minus_base_probability": round(cp - bp, 9),
                "base_unk_rank": b["statistics"]["processed"]["unk_rank"],
                "candidate_unk_rank": c["statistics"]["processed"]["unk_rank"],
                "base_unk_top1": b["statistics"]["processed"]["unk_is_top1"],
                "candidate_unk_top1": c["statistics"]["processed"]["unk_is_top1"],
            })
    return {
        "matched_pairs": len(comparisons),
        "candidate_higher_unk_probability": sum(r["candidate_minus_base_probability"] > 0 for r in comparisons),
        "candidate_lower_unk_probability": sum(r["candidate_minus_base_probability"] < 0 for r in comparisons),
        "mean_candidate_minus_base_probability": round(
            sum(r["candidate_minus_base_probability"] for r in comparisons) / len(comparisons), 9),
        "base_unk_top1_count": sum(r["base_unk_top1"] for r in comparisons),
        "candidate_unk_top1_count": sum(r["candidate_unk_top1"] for r in comparisons),
        "blank_prompt_index": 3,
        "blank_prompt_pairs": [r for r in comparisons if r["prompt_index"] == 3],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg_path = args.adapter / "adapter_config.json"
    weights = args.adapter / "adapter_model.safetensors"
    if not cfg_path.is_file() or not weights.is_file():
        parser.error("Exact rejected Run 12 Adapter required")
    if hashlib.sha256(weights.read_bytes()).hexdigest() != ADAPTER_SHA:
        parser.error("Adapter hash mismatch")
    if json.loads(cfg_path.read_text(encoding="utf-8")).get("base_model_name_or_path") != DEFAULT_MODEL:
        parser.error("Base model mismatch")
    prompts, holdout_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, PROMPTS)
    if len(prompts) != PROMPTS:
        raise ValueError("Expected four fixed prompts")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(42)
    torch.set_num_threads(2)
    source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(source), use_fast=True)
    unk_id = tokenizer.unk_token_id
    if unk_id is None:
        raise ValueError("Tokenizer lacks UNK")
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    rows = []

    def audit(model, phase):
        model.eval()
        for i, prompt in enumerate(prompts):
            prompt_ids = tokenizer(prompt, return_tensors="pt")["input_ids"][0].tolist()
            if len(prompt_ids) + STEPS > model.config.n_positions:
                raise ValueError("Context window exceeded")
            for step in range(STEPS):
                history = prompt_ids + [unk_id] * step
                with torch.inference_mode():
                    logits = model(
                        input_ids=torch.tensor([history], dtype=torch.long),
                        attention_mask=torch.ones((1, len(history)), dtype=torch.long),
                        use_cache=False,
                    ).logits[0, -1].float().tolist()
                rows.append({
                    "phase": phase, "prompt_index": i,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "forced_unk_count": step,
                    "statistics": measure_unk(logits, history, unk_id),
                })

    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    summary = compare_pairs(rows)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "matched forced-UNK history; no generated continuation",
        "source_training_run_id": 39921870784,
        "source_blank_token_audit_run_id": 40056542877,
        "model": DEFAULT_MODEL, "model_revision": DEFAULT_REVISION,
        "adapter_weights_sha256": ADAPTER_SHA, "holdout_sha256": holdout_sha,
        "device": "cpu", "seed": 42, "prompt_count": PROMPTS,
        "steps_per_prompt": STEPS, "forward_passes": len(rows),
        "input_contract": "input_ids + attention_mask; no token_type_ids",
        "logits_processing": "raw and repetition_penalty=1.12 on identical forced histories",
        "summary": summary, "rows": rows,
        "new_gpu_training": False, "new_model_answers": False,
        "promotion_approved": False,
        "limitations": "Forced UNK prefixes do not establish causal root cause, answer quality, or safety.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS:", len(rows), "CPU forwards;", summary["matched_pairs"], "matched pairs")


if __name__ == "__main__":
    main()
