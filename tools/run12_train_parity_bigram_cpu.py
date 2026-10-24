#!/usr/bin/env python3
"""Bounded CPU-only matched no-repeat-bigram audit; no training or promotion.

Run 12's previous 10-prompt bigram audit used a different input protocol.
This experiment tests four pinned train-parity prompts, 32 tokens each.
Only privacy-safe aggregates are exported, never prompts, token IDs or text.
"""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

PHASES = ("base", "candidate")
SETTINGS = ("control", "no_repeat_bigram")
PROMPT_COUNT = 4
MAX_NEW_TOKENS = 32


def summarize(rows):
    expected = {(phase, setting, index) for phase in PHASES
                for setting in SETTINGS for index in range(PROMPT_COUNT)}
    keys = [(row["phase"], row["setting"], row["prompt_index"]) for row in rows]
    if len(keys) != 16 or len(set(keys)) != 16 or set(keys) != expected:
        raise ValueError("Expected exactly 16 distinct paired generations")
    histories = {}
    for row in rows:
        index = row["prompt_index"]
        history = row["input_history_sha256"]
        if not isinstance(history, str) or len(history) != 64:
            raise ValueError("Missing or invalid input-history hash")
        histories.setdefault(index, set()).add(history)
        length = row["generated_token_count"]
        if type(length) is not int or not 1 <= length <= MAX_NEW_TOKENS:
            raise ValueError("Invalid generated token count")
        for field in ("period_count", "unk_count", "longest_period_run"):
            value = row[field]
            if type(value) is not int or not 0 <= value <= length:
                raise ValueError("Invalid token metric: " + field)
        if row["longest_period_run"] > row["period_count"]:
            raise ValueError("Period streak exceeds period count")
        if row["stop_reason"] not in ("eos", "max_new_tokens", "other"):
            raise ValueError("Invalid stop reason")
        if type(row["punctuation_only"]) is not bool or type(row["contains_chinese"]) is not bool:
            raise ValueError("Invalid text-classification flag")
        if set(row) != {"phase", "setting", "prompt_index", "input_history_sha256",
                        "generated_token_count", "period_count", "unk_count",
                        "longest_period_run", "stop_reason", "punctuation_only",
                        "contains_chinese"}:
            raise ValueError("Unexpected fields: possible raw output or sensitive data")
    if any(len(values) != 1 for values in histories.values()):
        raise ValueError("Control/candidate input histories differ")
    result = {}
    for phase in PHASES:
        for setting in SETTINGS:
            subset = [row for row in rows if row["phase"] == phase and row["setting"] == setting]
            result[f"{phase}/{setting}"] = {
                "n": PROMPT_COUNT,
                "period_tokens": sum(row["period_count"] for row in subset),
                "unk_tokens": sum(row["unk_count"] for row in subset),
                "max_period_streak": max(row["longest_period_run"] for row in subset),
                "punctuation_only": sum(row["punctuation_only"] for row in subset),
                "contains_chinese": sum(row["contains_chinese"] for row in subset),
                "eos": sum(row["stop_reason"] == "eos" for row in subset),
                "max_token_limit": sum(row["stop_reason"] == "max_new_tokens" for row in subset),
            }
    return result


def verify_historical_control(summary):
    """Fail closed if controls drift from 40109722670; no invalid comparison."""
    base = summary["base/control"]
    candidate = summary["candidate/control"]
    if (base["period_tokens"], base["unk_tokens"], base["max_period_streak"],
        base["max_token_limit"]) != (0, 1, 0, 4):
        raise ValueError("Base control differs from Run 40109722670")
    if (candidate["period_tokens"], candidate["unk_tokens"],
        candidate["max_period_streak"], candidate["max_token_limit"],
        candidate["eos"]) != (64, 32, 32, 3, 1):
        raise ValueError("Candidate control differs from Run 40109722670")


def main():
    from generation_decode_probe import analyze_tokens, read_prompts
    from run12_direct_answer_generation import verify_adapter
    from run12_free_period_trajectory import longest_period_run
    from run12_token_type_parity import make_inputs
    from run12_tokenized_direct_answer_audit import ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, EVAL_SHA256, limit=PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        parser.error("Exactly four pinned prompts required")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.cuda.is_available():
        parser.error("CUDA is visible; CPU-only experiment refused")
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    period_ids = tokenizer.encode(".", add_special_tokens=False)
    if len(period_ids) != 1 or period_ids[0] in tokenizer.all_special_ids:
        parser.error("Period is not a single non-special token")
    period_id = period_ids[0]
    base = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        parser.error("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def audit(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = make_inputs(tokenizer, prompt, "train_parity")
            history = inputs["input_ids"][0].tolist()
            if len(history) + MAX_NEW_TOKENS > model.config.n_positions:
                raise ValueError("Model context window exceeded")
            history_hash = hashlib.sha256(json.dumps(history).encode("ascii")).hexdigest()
            for setting, ngram_size in (("control", 0), ("no_repeat_bigram", 2)):
                torch.manual_seed(42 + index)
                with torch.inference_mode():
                    output = model.generate(
                        **inputs, do_sample=False, max_new_tokens=MAX_NEW_TOKENS,
                        repetition_penalty=1.12, no_repeat_ngram_size=ngram_size,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                ids = output[0][len(history):].tolist()
                diagnostic = analyze_tokens(ids, tokenizer, MAX_NEW_TOKENS, include_text=False)
                decoded = tokenizer.decode(ids, skip_special_tokens=True)
                rows.append({
                    "phase": phase, "setting": setting, "prompt_index": index,
                    "input_history_sha256": history_hash,
                    "generated_token_count": len(ids),
                    "period_count": ids.count(period_id),
                    "unk_count": ids.count(tokenizer.unk_token_id),
                    "longest_period_run": longest_period_run(ids, period_id),
                    "stop_reason": diagnostic["stop_reason_inferred"],
                    "punctuation_only": bool(diagnostic["punctuation_only"]),
                    "contains_chinese": bool(re.search(r"[\u3400-\u9fff]", decoded)),
                })

    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    summary = summarize(rows)
    verify_historical_control(summary)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        "code_sha": os.environ.get("GITHUB_SHA"),
        "source_gpu_run_id": 39921870784,
        "historical_control_run_id": 40109722670,
        "previous_noncomparable_bigram_run_id": 40016790586,
        "model_revision": MODEL_REVISION,
        "adapter_sha256": ADAPTER_SHA256,
        "eval_sha256": eval_sha,
        "device": "cpu", "new_gpu_training": False,
        "config": {"prompt_count": PROMPT_COUNT, "generations": len(rows),
                   "max_new_tokens": MAX_NEW_TOKENS, "do_sample": False,
                   "repetition_penalty": 1.12, "seed_per_prompt": "42+index",
                   "input_mode": "train_parity", "only_variable": "no_repeat_ngram_size 0 vs 2"},
        "summary": summary, "rows": rows,
        "promotion_approved": False,
        "quality_certified": False,
        "limitations": "No raw text or token IDs exported. Chinese character presence is not relevance, readability, or safety certification.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: 16 matched CPU generations, controls match Run 40109722670; no GPU or promotion")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
