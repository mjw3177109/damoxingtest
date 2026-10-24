#!/usr/bin/env python3
"""Read-only CPU first-token punctuation/UNK/EOS audit of rejected Run 12."""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

PHASES = ("base", "candidate")
SETTINGS = ("control", "direct_answer")
PROMPT_COUNT = 4
PUNCTUATION = ".。!！?？,，;；:："

def category_ids(tokenizer, vocab_size):
    unk, eos = tokenizer.unk_token_id, tokenizer.eos_token_id
    if unk is None or eos is None or unk == eos:
        raise ValueError("Distinct UNK and EOS tokens required")
    if any(type(i) is not int or i < 0 or i >= vocab_size for i in (unk, eos)):
        raise ValueError("Special token outside vocabulary")
    punctuation = set()
    for char in PUNCTUATION:
        ids = tokenizer.encode(char, add_special_tokens=False)
        if len(ids) == 1 and ids[0] not in (unk, eos):
            if type(ids[0]) is not int or not 0 <= ids[0] < vocab_size:
                raise ValueError("Punctuation ID outside vocabulary")
            punctuation.add(ids[0])
    if not punctuation:
        raise ValueError("No valid single-token punctuation")
    return {"unk": {unk}, "eos": {eos}, "punctuation": punctuation}

def measure_categories(logits, categories):
    values = [float(x) for x in logits]
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite or empty logits")
    if set(categories) != {"unk", "eos", "punctuation"}:
        raise ValueError("Unexpected categories")
    seen = set()
    for ids in categories.values():
        if not ids or any(type(i) is not int or not 0 <= i < len(values) for i in ids):
            raise ValueError("Invalid category IDs")
        if seen.intersection(ids):
            raise ValueError("Overlapping categories")
        seen.update(ids)
    peak = max(values)
    weights = [math.exp(v - peak) for v in values]
    denom = sum(weights)
    top = max(range(len(values)), key=lambda i: values[i])
    result = {"top1_category": next((name for name, ids in categories.items() if top in ids), "other"),
              "top1_probability": round(weights[top] / denom, 9)}
    for name, ids in categories.items():
        result[name + "_probability"] = round(sum(weights[i] for i in ids) / denom, 9)
        best = max(values[i] for i in ids)
        result[name + "_best_rank"] = 1 + sum(v > best for v in values)
    return result

def summarize(rows):
    expected = {(p, s, i) for p in PHASES for s in SETTINGS for i in range(PROMPT_COUNT)}
    keys = [(r["phase"], r["setting"], r["prompt_index"]) for r in rows]
    if len(keys) != len(expected) or len(set(keys)) != len(expected) or set(keys) != expected:
        raise ValueError("Expected 16 unique observations")
    by_key = dict(zip(keys, rows))
    for setting in SETTINGS:
        for i in range(PROMPT_COUNT):
            if by_key["base", setting, i]["prompt_sha256"] != by_key["candidate", setting, i]["prompt_sha256"]:
                raise ValueError("Model prompt mismatch")
    comparisons = []
    for phase in PHASES:
        for i in range(PROMPT_COUNT):
            before = by_key[phase, "control", i]
            after = by_key[phase, "direct_answer", i]
            if before["prompt_sha256"] == after["prompt_sha256"]:
                raise ValueError("Prompt variant unchanged")
            delta = {name: round(after["processed"][name + "_probability"] - before["processed"][name + "_probability"], 9)
                     for name in ("unk", "eos", "punctuation")}
            comparisons.append({"phase": phase, "prompt_index": i, "processed_probability_delta": delta,
                                "control_top1": before["processed"]["top1_category"],
                                "variant_top1": after["processed"]["top1_category"]})
    return {"paired_comparisons": len(comparisons), "comparisons": comparisons,
            "mean_variant_minus_control": {
                phase: {name: round(sum(c["processed_probability_delta"][name] for c in comparisons if c["phase"] == phase) / PROMPT_COUNT, 9)
                        for name in ("unk", "eos", "punctuation")}
                for phase in PHASES}}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", default=Path("data/safety_humanity_eval_v1.jsonl"), type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    from first_token_probability_probe import apply_repetition_penalty
    from generation_decode_probe import read_prompts
    from run12_direct_answer_generation import verify_adapter
    from run12_token_type_parity import make_inputs
    from run12_tokenized_direct_answer_audit import (
        ADAPTER_SHA256, EVAL_SHA256, MODEL, MODEL_REVISION,
        compare_prompt, variant_prompt,
    )
    verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, EVAL_SHA256, limit=PROMPT_COUNT)
    if len(prompts) != PROMPT_COUNT:
        parser.error("Exactly four pinned prompts required")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.cuda.is_available():
        parser.error("CPU-only diagnostic: CUDA is visible")
    torch.set_num_threads(2)
    tokenizer = AutoTokenizer.from_pretrained(str(args.adapter), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if not all(compare_prompt(prompt, tokenizer)["token_sequence_changed"] for prompt in prompts):
        parser.error("Prompt variant does not change input tokens")
    base = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REVISION).cpu().eval()
    vocab_size = base.get_input_embeddings().num_embeddings
    if vocab_size != len(tokenizer):
        parser.error("Tokenizer/model vocabulary mismatch")
    categories = category_ids(tokenizer, vocab_size)
    rows = []
    def audit(model, phase):
        model.eval()
        for index, control in enumerate(prompts):
            for setting in SETTINGS:
                prompt = control if setting == "control" else variant_prompt(control)
                inputs = make_inputs(tokenizer, prompt, "train_parity")
                history = inputs["input_ids"][0].tolist()
                if len(history) >= model.config.n_positions:
                    raise ValueError("Prompt exceeds context")
                with torch.inference_mode():
                    logits = model(**inputs, use_cache=False).logits[0, -1].float().cpu().tolist()
                adjusted = apply_repetition_penalty(logits, history, penalty=1.12)
                rows.append({"phase": phase, "setting": setting, "prompt_index": index,
                             "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                             "raw": measure_categories(logits, categories),
                             "processed": measure_categories(adjusted, categories)})
    audit(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).cpu().eval()
    audit(candidate, "candidate")
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "actions_run_id": os.environ.get("GITHUB_RUN_ID"), "code_sha": os.environ.get("GITHUB_SHA"),
              "source_training_run_id": 39921870784, "previous_generation_run_id": 40088294558,
              "model": MODEL, "model_revision": MODEL_REVISION,
              "adapter_sha256": ADAPTER_SHA256, "holdout_sha256": eval_sha,
              "device": "cpu", "forward_passes": len(rows), "new_gpu_training": False,
              "new_model_answers": False, "promotion_approved": False,
              "experiment": "first-step category probability: base vs rejected LoRA; control vs direct-answer directive",
              "processor": "raw and repetition_penalty=1.12; no token_type_ids",
              "punctuation_group_size": len(categories["punctuation"]),
              "summary": summarize(rows), "rows": rows,
              "limitations": "Only four prompts and first-step probabilities. No answer-quality improvement or causal root cause established."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS:", len(rows), "bounded CPU forwards; no training or promotion")

if __name__ == "__main__":
    main()
