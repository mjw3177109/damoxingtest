#!/usr/bin/env python3
"""Read-only CPU Run 12 greedy comparison: historical default vs training-parity
prompt encoding. No training, Kaggle submission, promotion, or raw text export.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION, analyze_tokens, read_prompts,
)
from run12_temperature_pair_cpu import verify_adapter

ARMS = ("historical_default", "training_parity")


def generation_kwargs(tokenizer, max_new_tokens=64):
    if type(max_new_tokens) is not int or max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    return {
        "max_new_tokens": max_new_tokens, "do_sample": False,
        "repetition_penalty": 1.12, "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }


def summarize(rows):
    if len(rows) != 20:
        raise ValueError("Exactly 10 paired prompts per arm required")
    by_arm = {arm: {} for arm in ARMS}
    for row in rows:
        arm, index, digest = row.get("arm"), row.get("prompt_index"), row.get("prompt_sha256")
        if arm not in by_arm or type(index) is not int or not 0 <= index < 10:
            raise ValueError("Invalid arm or prompt index")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("Invalid prompt provenance")
        if index in by_arm[arm]:
            raise ValueError("Duplicate prompt in arm")
        by_arm[arm][index] = row
    if any(set(group) != set(range(10)) for group in by_arm.values()):
        raise ValueError("Incomplete paired prompts")
    for index in range(10):
        if by_arm[ARMS[0]][index]["prompt_sha256"] != by_arm[ARMS[1]][index]["prompt_sha256"]:
            raise ValueError("Unpaired prompt content")
    out = {}
    for arm in ARMS:
        group = list(by_arm[arm].values())
        out[arm] = {
            "samples": len(group),
            "punctuation_only_count": sum(bool(x["punctuation_only"]) for x in group),
            "eos_count": sum(x["stop_reason_inferred"] == "eos" for x in group),
            "max_identical_character_run": max(x["longest_identical_character_run"] for x in group),
            "mean_generated_token_count": round(
                sum(x["generated_token_count"] for x in group) / len(group), 3),
            "direct_answer_count": None,
            "human_review_required": True,
        }
    out["paired_input_id_differences"] = sum(
        by_arm[ARMS[0]][i]["input_token_id_sha256"] != by_arm[ARMS[1]][i]["input_token_id_sha256"]
        for i in range(10))
    out["paired_output_id_differences"] = sum(
        by_arm[ARMS[0]][i]["output_token_id_sha256"] != by_arm[ARMS[1]][i]["output_token_id_sha256"]
        for i in range(10))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-new-tokens", type=int, default=64)
    args = p.parse_args()
    if args.max_new_tokens < 1:
        p.error("max_new_tokens must be positive")
    adapter_hash = verify_adapter(args.adapter)
    prompts, eval_hash = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=10)
    if len(prompts) != 10:
        raise ValueError("Expected exactly ten fixed prompts")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").exists() else DEFAULT_MODEL
    tokenizer_options = {"use_fast": True}
    if tokenizer_source == DEFAULT_MODEL:
        tokenizer_options["revision"] = DEFAULT_REVISION
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), **tokenizer_options)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.pad_token_id is None or tokenizer.eos_token_id is None:
        raise ValueError("Tokenizer PAD/EOS missing")
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).to("cpu")
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    model = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).to("cpu")
    model.eval()
    settings = generation_kwargs(tokenizer, args.max_new_tokens)
    rows = []
    for index, prompt in enumerate(prompts):
        for arm in ARMS:
            # The encoding switch is the sole experimental variable.
            options = {"add_special_tokens": False} if arm == "training_parity" else {}
            inputs = tokenizer(prompt, return_tensors="pt", **options)
            with torch.inference_mode():
                generated = model.generate(**inputs, **settings)
            token_ids = generated[0][inputs["input_ids"].shape[1]:].tolist()
            metrics = analyze_tokens(token_ids, tokenizer, args.max_new_tokens)
            metrics.pop("token_ids", None)
            rows.append({
                "arm": arm, "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "input_token_count": int(inputs["input_ids"].shape[1]),
                "input_token_id_sha256": hashlib.sha256(
                    json.dumps(inputs["input_ids"][0].tolist()).encode()).hexdigest(),
                "output_token_id_sha256": hashlib.sha256(json.dumps(token_ids).encode()).hexdigest(),
                **metrics,
            })
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": "39921870784", "adapter_sha256": adapter_hash,
        "holdout_sha256": eval_hash, "model": DEFAULT_MODEL,
        "model_revision": DEFAULT_REVISION, "device": "cpu",
        "decoding": "greedy", "max_new_tokens": args.max_new_tokens,
        "generation_parameters": {"do_sample": False, "repetition_penalty": 1.12},
        "summary": summarize(rows), "per_prompt_diagnostics": rows,
        "promotion_approved": False,
        "interpretation": "Paired diagnostic only; lexical metrics cannot certify semantic quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved 20 CPU-only paired greedy generations; no training or promotion")


if __name__ == "__main__":
    main()
