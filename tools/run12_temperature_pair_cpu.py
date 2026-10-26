#!/usr/bin/env python3
"""Read-only, CPU-only Run-12 LoRA temperature comparison (0.8 versus 0.7).

No training, Kaggle submission, promotion, or automatic quality approval.
Default output contains only per-prompt numeric aggregates and prompt hashes.
"""
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

EXPECTED_ADAPTER_SHA256 = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"
TEMPERATURES = (0.8, 0.7)


def verify_adapter(adapter, expected_sha256=EXPECTED_ADAPTER_SHA256):
    """Fail closed before importing heavyweight inference dependencies."""
    adapter = Path(adapter)
    if not (adapter / "adapter_config.json").is_file():
        raise ValueError("Missing adapter_config.json")
    weights = adapter / "adapter_model.safetensors"
    if not weights.is_file():
        raise ValueError("Missing adapter_model.safetensors")
    digest = hashlib.sha256()
    with weights.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise ValueError("Adapter SHA-256 mismatch; refusing non-comparable experiment")
    return actual


def generation_settings(temperature, max_new_tokens, tokenizer):
    if temperature not in TEMPERATURES:
        raise ValueError("Only the pre-registered 0.8/0.7 temperatures are permitted")
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    return {
        "do_sample": True,
        "temperature": temperature,
        "top_p": 0.9,
        "no_repeat_ngram_size": 3,
        "repetition_penalty": 1.12,
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }


def summarize(rows, temperatures=TEMPERATURES):
    """Aggregate diagnostic signals only; semantic success requires human review."""
    summary = {}
    for temperature in temperatures:
        group = [r for r in rows if r["temperature"] == temperature]
        if not group:
            raise ValueError("Missing comparison arm")
        summary[str(temperature)] = {
            "samples": len(group),
            "punctuation_only_count": sum(bool(r["punctuation_only"]) for r in group),
            "eos_count": sum(r["stop_reason_inferred"] == "eos" for r in group),
            "max_identical_character_run": max(r["longest_identical_character_run"] for r in group),
            "mean_generated_token_count": round(sum(r["generated_token_count"] for r in group) / len(group), 3),
            "direct_answer_count": None,
            "human_review_required": True,
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    args = parser.parse_args()
    if args.max_new_tokens < 1:
        parser.error("max_new_tokens must be positive")
    adapter_sha = verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=10)
    if len(prompts) != 10:
        parser.error("The fixed holdout must supply exactly 10 prompts")

    # Heavy dependencies are intentionally imported only for real inference.
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").exists() else DEFAULT_MODEL
    tokenizer_kwargs = {"use_fast": True}
    if tokenizer_source == DEFAULT_MODEL:
        tokenizer_kwargs["revision"] = DEFAULT_REVISION
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), **tokenizer_kwargs)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.pad_token_id is None or tokenizer.eos_token_id is None:
        raise ValueError("Tokenizer lacks required PAD/EOS tokens")
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).to("cpu")
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer and model vocabulary sizes differ")
    base.config.pad_token_id = tokenizer.pad_token_id
    model = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).to("cpu")
    model.eval()
    rows = []
    for index, prompt in enumerate(prompts):
        inputs = tokenizer(prompt, return_tensors="pt")
        for temperature in TEMPERATURES:
            # Same seed and same inputs for both arms. Never use CUDA/GPU.
            torch.manual_seed(args.seed + index)
            settings = generation_settings(temperature, args.max_new_tokens, tokenizer)
            with torch.inference_mode():
                generated = model.generate(**inputs, **settings)
            ids = generated[0][inputs["input_ids"].shape[1]:].tolist()
            metrics = analyze_tokens(ids, tokenizer, args.max_new_tokens)
            metrics.pop("token_ids", None)  # Avoid storing reversible output content.
            rows.append({
                "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "temperature": temperature,
                **metrics,
            })
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": "39921870784",
        "adapter_sha256": adapter_sha,
        "holdout_sha256": eval_sha,
        "model": DEFAULT_MODEL,
        "model_revision": DEFAULT_REVISION,
        "device": "cpu",
        "seed": args.seed,
        "max_new_tokens": args.max_new_tokens,
        "fixed_parameters": {"top_p": 0.9, "no_repeat_ngram_size": 3, "repetition_penalty": 1.12},
        "temperatures": list(TEMPERATURES),
        "summary": summarize(rows),
        "per_prompt_diagnostics": rows,
        "promotion_approved": False,
        "interpretation": "Read-only inference; semantic direct-answer rate requires separate human review.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved CPU-only temperature comparison for", len(prompts), "prompts")


if __name__ == "__main__":
    main()
