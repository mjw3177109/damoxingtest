#!/usr/bin/env python3
"""CPU-only paired greedy decoding audit; never trains or approves adapters."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256,
    DEFAULT_MODEL,
    DEFAULT_REVISION,
    analyze_tokens,
    read_prompts,
)


def summarize(rows):
    expected = {(phase, setting, index) for phase in ("base", "candidate")
                for setting in ("control", "no_repeat_bigram") for index in range(10)}
    keys = [(r["phase"], r["setting"], r["prompt_index"]) for r in rows]
    if len(keys) != 40 or set(keys) != expected or len(set(keys)) != 40:
        raise ValueError("Expected exactly 40 distinct paired observations")
    summary = {}
    for phase in ("base", "candidate"):
        for setting in ("control", "no_repeat_bigram"):
            subset = [r for r in rows if r["phase"] == phase and r["setting"] == setting]
            summary[f"{phase}/{setting}"] = {
                "count": len(subset),
                "punctuation_only": sum(bool(r["punctuation_only"]) for r in subset),
                "eos": sum(r["stop_reason_inferred"] == "eos" for r in subset),
                "max_token_limit": sum(r["stop_reason_inferred"] == "max_new_tokens" for r in subset),
                "mean_longest_character_run": round(sum(r["longest_identical_character_run"] for r in subset) / 10, 2),
            }
    return summary


def verify_historical_control(summary):
    # Audited Run 39950178751: base/greedy 7/10, candidate/greedy 10/10 punctuation.
    # Reject non-comparable runs rather than claiming improvement.
    if summary["base/control"]["punctuation_only"] != 7:
        raise ValueError("Base greedy control diverges from audited Run 39950178751")
    if summary["candidate/control"]["punctuation_only"] != 10:
        raise ValueError("Candidate greedy control diverges from audited Run 39950178751")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", default=Path("data/safety_humanity_eval_v1.jsonl"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not (args.adapter / "adapter_config.json").is_file():
        parser.error("Run 12 candidate Adapter missing")
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
        raise RuntimeError("Tokenizer/model vocab mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def evaluate(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = tokenizer(prompt, return_tensors="pt")
            for setting, no_repeat in (("control", 0), ("no_repeat_bigram", 2)):
                torch.manual_seed(args.seed + index)
                with torch.inference_mode():
                    output = model.generate(
                        **inputs, do_sample=False, max_new_tokens=64,
                        repetition_penalty=1.12, no_repeat_ngram_size=no_repeat,
                        pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                    )
                ids = output[0][inputs["input_ids"].shape[1]:].tolist()
                diagnostic = analyze_tokens(ids, tokenizer, 64, include_text=False)
                diagnostic.pop("token_ids")  # minimize stored data; no raw prompts/answers
                rows.append({
                    "phase": phase, "setting": setting, "prompt_index": index,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    **diagnostic,
                })

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    evaluate(candidate, "candidate")
    summary = summarize(rows)
    verify_historical_control(summary)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": "39921870784",
        "historical_control_run_id": "39950178751",
        "model_revision": DEFAULT_REVISION,
        "holdout_sha256": holdout_sha,
        "device": "cpu",
        "seed": args.seed,
        "experiment": "greedy only, repetition_penalty=1.12; only no_repeat_ngram_size 0 vs 2 changes",
        "new_model_generations": 40,
        "summary": summary,
        "results": rows,
        "quality_assessment": "UNVERIFIED: punctuation avoidance is not correctness, readability, safety or model improvement",
        "promotion_approved": False,
        "gpu_training_performed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
