#!/usr/bin/env python3
"""Read-only first-token probability audit for the rejected Run 12 Adapter.

No training, no raw prompt/output text, no promotion or model changes.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256,
    DEFAULT_MODEL,
    DEFAULT_REVISION,
    read_prompts,
)

WATCH_IDS = (119, 136, 8601)


def summarize_logits(logits, watch_ids=WATCH_IDS, top_k=5):
    """Compute a stable softmax summary without storing full logits."""
    values = [float(x) for x in logits]
    if not values or not all(math.isfinite(x) for x in values):
        raise ValueError("Non-finite or empty model logits")
    if top_k < 1:
        raise ValueError("top_k must be positive")
    maximum = max(values)
    weights = [math.exp(x - maximum) for x in values]
    denominator = sum(weights)
    probabilities = [w / denominator for w in weights]
    ranked = sorted(range(len(values)), key=lambda i: (-values[i], i))
    rank_map = {token_id: rank + 1 for rank, token_id in enumerate(ranked)}
    return {
        "top_k": [
            {"token_id": i, "probability": round(probabilities[i], 9)}
            for i in ranked[:top_k]
        ],
        "entropy_nats": round(
            -sum(p * math.log(p) for p in probabilities if p > 0), 7
        ),
        "watch": {
            str(i): {
                "probability": round(probabilities[i], 9),
                "rank": rank_map[i],
            }
            for i in watch_ids if 0 <= i < len(values)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=DEFAULT_REVISION)
    parser.add_argument("--expected-eval-sha256", default=DEFAULT_EVAL_SHA256)
    args = parser.parse_args()

    adapter_config = args.adapter / "adapter_config.json"
    adapter_weights = args.adapter / "adapter_model.safetensors"
    if not adapter_config.is_file() or not adapter_weights.is_file():
        parser.error("Exact candidate Adapter config and weights are required")
    cfg = json.loads(adapter_config.read_text(encoding="utf-8"))
    if cfg.get("base_model_name_or_path") != args.model:
        parser.error("Candidate Adapter base model does not match pinned model")
    prompts, holdout_sha = read_prompts(args.eval_data, args.expected_eval_sha256, 10)
    if len(prompts) != 10:
        raise ValueError("Expected exactly 10 fixed holdout prompts")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Always CPU; no GPU allocation and no generation or weight updates.
    torch.set_num_threads(2)
    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else args.model
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(args.model, revision=args.model_revision)
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer and model vocabulary sizes differ")
    base.eval()

    rows = []
    def measure(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = tokenizer(prompt, return_tensors="pt")
            if inputs["input_ids"].shape[1] > model.config.n_positions:
                raise ValueError("Prompt exceeds model context window")
            with torch.inference_mode():
                last_logits = model(**inputs, use_cache=False).logits[0, -1].float().cpu().tolist()
            rows.append({
                "phase": phase,
                "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                **summarize_logits(last_logits),
            })

    measure(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    measure(candidate, "candidate")

    by_key = {(r["phase"], r["prompt_index"]): r for r in rows}
    comparisons = []
    for index in range(10):
        before = by_key[("base", index)]
        after = by_key[("candidate", index)]
        comparisons.append({
            "prompt_index": index,
            "base_top1_id": before["top_k"][0]["token_id"],
            "candidate_top1_id": after["top_k"][0]["token_id"],
            "top1_changed": before["top_k"][0]["token_id"] != after["top_k"][0]["token_id"],
            "entropy_delta_nats": round(after["entropy_nats"] - before["entropy_nats"], 7),
            "watch_probability_delta": {
                str(i): round(after["watch"][str(i)]["probability"] - before["watch"][str(i)]["probability"], 9)
                for i in WATCH_IDS
            },
        })

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": "39921870784",
        "source_decode_probe_run_id": "39950178751",
        "model": args.model,
        "model_revision": args.model_revision,
        "holdout_sha256": holdout_sha,
        "candidate_adapter_weights_sha256": hashlib.sha256(adapter_weights.read_bytes()).hexdigest(),
        "device": "cpu",
        "prompt_count": len(prompts),
        "model_forward_passes": len(rows),
        "watch_token_ids": list(WATCH_IDS),
        "rows": rows,
        "comparisons": comparisons,
        "model_promotion_approved": False,
        "limitations": [
            "Read-only next-token probabilities, not generated answers or training metrics.",
            "Probabilities depend on the pinned model, tokenizer, prompt, and candidate Adapter.",
            "No raw prompt/output text is included; token IDs are not decoded here.",
            "This audit alone does not establish model quality, safety, or a causal root cause.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", len(rows), "read-only first-token distributions to", args.output)


if __name__ == "__main__":
    main()
