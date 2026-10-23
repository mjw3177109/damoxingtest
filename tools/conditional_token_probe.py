#!/usr/bin/env python3
"""Bounded CPU-only 8-step greedy token audit for rejected Run 12.

No training, model promotion, raw prompt text, decoded output, or secrets.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

WATCH_IDS = (119, 136)


def adjust_repetition(logits, seen_ids, penalty=1.12):
    """Match Hugging Face repetition-penalty score transformation."""
    if not math.isfinite(penalty) or penalty <= 0:
        raise ValueError("Invalid repetition penalty")
    result = [float(x) for x in logits]
    if not result or not all(math.isfinite(x) for x in result):
        raise ValueError("Empty or non-finite logits")
    for token_id in set(seen_ids):
        if not isinstance(token_id, int) or token_id < 0 or token_id >= len(result):
            raise ValueError("Invalid token in history")
        score = result[token_id]
        result[token_id] = score * penalty if score < 0 else score / penalty
    return result


def token_probability(logits, token_id):
    if token_id < 0 or token_id >= len(logits):
        return None
    maximum = max(logits)
    return math.exp(logits[token_id] - maximum) / sum(math.exp(v - maximum) for v in logits)


def trace_greedy(initial_ids, forward_logits, eos_ids=(), steps=8, penalty=1.12):
    """Use one bounded full-context forward per step; return IDs/probabilities only."""
    if not initial_ids or steps < 1 or steps > 8:
        raise ValueError("Expected nonempty prompt and 1..8 steps")
    history = list(initial_ids)
    generated = []
    rows = []
    eos = set(eos_ids)
    for step in range(steps):
        raw = [float(v) for v in forward_logits(history)]
        processed = adjust_repetition(raw, history, penalty)
        raw_top1 = max(range(len(raw)), key=lambda i: raw[i])
        top1 = max(range(len(processed)), key=lambda i: processed[i])
        rows.append({
            "step": step + 1,
            "raw_top1_id": raw_top1,
            "processed_top1_id": top1,
            "selected_token_id": top1,
            "processed_top1_probability": round(token_probability(processed, top1), 9),
            "raw_to_processed_top1_changed": raw_top1 != top1,
            "same_as_previous_generated": bool(generated) and top1 == generated[-1],
            "same_as_first_generated": bool(generated) and top1 == generated[0],
            "watch_probabilities": {
                str(i): round(token_probability(processed, i), 9)
                for i in WATCH_IDS if i < len(processed)
            },
            "eos": top1 in eos,
        })
        generated.append(top1)
        history.append(top1)
        if top1 in eos:
            break
    return {
        "steps_executed": len(rows),
        "selected_token_ids": generated,
        "stop_reason": "eos" if generated[-1] in eos else "bounded_steps",
        "same_token_all_steps": len(set(generated)) == 1,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from generation_decode_probe import DEFAULT_MODEL, DEFAULT_REVISION, DEFAULT_EVAL_SHA256, read_prompts
    if not (args.adapter / "adapter_config.json").is_file() or not (args.adapter / "adapter_model.safetensors").is_file():
        parser.error("Exact rejected Run 12 Adapter config and weights are required")
    cfg = json.loads((args.adapter / "adapter_config.json").read_text(encoding="utf-8"))
    if cfg.get("base_model_name_or_path") != DEFAULT_MODEL:
        parser.error("Adapter base model mismatch")
    prompts, holdout_hash = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, 4)
    if len(prompts) != 4:
        raise ValueError("Expected four fixed holdout prompts")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(2)
    source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(source), use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION)
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    base.eval()
    eos_ids = (tokenizer.eos_token_id,) if tokenizer.eos_token_id is not None else ()
    results = []

    def measure(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            prompt_ids = tokenizer(prompt, return_tensors="pt")["input_ids"][0].tolist()
            if len(prompt_ids) + 8 > model.config.n_positions:
                raise ValueError("Prompt plus probe exceeds context window")
            def forward(history):
                with torch.inference_mode():
                    return model(input_ids=torch.tensor([history]), use_cache=False).logits[0, -1].float().tolist()
            trace = trace_greedy(prompt_ids, forward, eos_ids=eos_ids)
            results.append({
                "phase": phase,
                "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                **trace,
            })

    measure(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    measure(candidate, "candidate")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": "39921870784",
        "model": DEFAULT_MODEL,
        "model_revision": DEFAULT_REVISION,
        "holdout_sha256": holdout_hash,
        "adapter_weights_sha256": hashlib.sha256((args.adapter / "adapter_model.safetensors").read_bytes()).hexdigest(),
        "device": "cpu",
        "decode_mode": "greedy; repetition_penalty=1.12; use_cache=False",
        "prompt_count": 4,
        "max_steps": 8,
        "model_forward_passes": sum(row["steps_executed"] for row in results),
        "results": results,
        "model_promotion_approved": False,
        "limitations": [
            "Token-level read-only diagnostic, not a training or quality result.",
            "Four fixed prompts, first eight tokens only; cannot prove causal root cause.",
            "No decoded answers, prompt text, credentials, or personal data saved.",
            "No new Train Loss, Val Loss, PPL or GPU allocation.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", len(results), "bounded CPU-only token traces to", args.output)


if __name__ == "__main__":
    main()
