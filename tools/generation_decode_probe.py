#!/usr/bin/env python3
"""Read-only base-vs-LoRA generation probe for an existing candidate Adapter.

Does not train, push to Kaggle, or promote models. Requires an extracted Adapter.
Default report contains token IDs and lexical aggregates but no raw prompts/outputs.
"""
import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODEL = "uer/gpt2-chinese-cluecorpussmall"
DEFAULT_REVISION = "c2c0249d8a2731f269414cc3b22dff021f8e07a3"
DEFAULT_EVAL_SHA256 = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"


def read_prompts(path, expected_sha256=DEFAULT_EVAL_SHA256, limit=10):
    payload = Path(path).read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if expected_sha256 and actual_sha != expected_sha256:
        raise ValueError("Holdout file SHA-256 mismatch; refusing non-comparable probe")
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if not rows or limit < 1:
        raise ValueError("No evaluation prompts requested")
    prompts = []
    for row in rows[:limit]:
        if not isinstance(row, dict) or not isinstance(row.get("instruction"), str) or not row["instruction"].strip():
            raise ValueError("Evaluation record lacks an instruction")
        prompts.append("用户：" + row["instruction"] + "\n助手：")
    return prompts, actual_sha


def longest_run(text):
    best = current = 0
    prev = None
    for ch in text:
        current = current + 1 if ch == prev else 1
        best = max(best, current)
        prev = ch
    return best


def analyze_tokens(token_ids, tokenizer, max_new_tokens, include_text=False):
    ids = [int(i) for i in token_ids]
    eos_id = tokenizer.eos_token_id
    if isinstance(eos_id, (tuple, list)):
        eos_ids = set(eos_id)
    else:
        eos_ids = {eos_id} if eos_id is not None else set()
    eos_position = next((i for i, value in enumerate(ids) if value in eos_ids), None)
    stop_reason = "eos" if eos_position is not None else ("max_new_tokens" if len(ids) >= max_new_tokens else "other")
    text = tokenizer.decode(ids, skip_special_tokens=True).strip()
    counts = Counter(text)
    report = {
        "token_ids": ids,
        "generated_token_count": len(ids),
        "eos_position": eos_position,
        "stop_reason_inferred": stop_reason,
        "character_count": len(text),
        "distinct_characters": len(counts),
        "longest_identical_character_run": longest_run(text),
        "punctuation_only": bool(text) and all(unicodedata.category(ch).startswith("P") for ch in text),
    }
    if include_text:
        report["output"] = text
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True, help="Extracted run-12 candidate Adapter directory")
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--expected-eval-sha256", default=DEFAULT_EVAL_SHA256)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-revision", default=DEFAULT_REVISION)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--include-text", action="store_true", help="Include raw model output in local report")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.adapter / "adapter_config.json").is_file():
        parser.error("Adapter directory must contain adapter_config.json")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be positive")
    prompts, eval_hash = read_prompts(args.eval_data, args.expected_eval_sha256, args.limit)

    # Heavy dependencies are intentionally imported only for an actual inference run.
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").exists() else args.model
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = AutoModelForCausalLM.from_pretrained(args.model, revision=args.model_revision).to(device)
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer and base model vocabulary sizes differ; inspect before running")
    base.config.use_cache = True
    base.config.pad_token_id = tokenizer.pad_token_id
    base.eval()
    rows = []

    def run_phase(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            for mode in ("greedy", "sample"):
                torch.manual_seed(args.seed + index)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(args.seed + index)
                kwargs = dict(
                    max_new_tokens=args.max_new_tokens,
                    do_sample=(mode == "sample"),
                    repetition_penalty=1.12,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
                if mode == "sample":
                    kwargs.update(temperature=0.8, top_p=0.9, no_repeat_ngram_size=3)
                with torch.inference_mode():
                    result = model.generate(**inputs, **kwargs)
                generated = result[0][inputs["input_ids"].shape[1]:].tolist()
                row = {
                    "phase": phase,
                    "decode_mode": mode,
                    "prompt_index": index,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    **analyze_tokens(generated, tokenizer, args.max_new_tokens, args.include_text),
                }
                rows.append(row)

    run_phase(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    run_phase(candidate, "candidate")
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run_id": "39921870784",
        "model": args.model,
        "model_revision": args.model_revision,
        "holdout_sha256": eval_hash,
        "seed": args.seed,
        "max_new_tokens": args.max_new_tokens,
        "device": device,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "results": rows,
        "interpretation": "Controlled inference diagnostics only; no training, quality certification, or promotion.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", len(rows), "diagnostic generations to", args.output)


if __name__ == "__main__":
    main()
