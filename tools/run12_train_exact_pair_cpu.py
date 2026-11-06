#!/usr/bin/env python3
"""CPU-only Run 12 candidate comparison: historical train_parity vs train_exact.

Only the prompt encoding changes. No GPU, training, promotion, raw prompt or
generated-text export. Historical train_parity remains unchanged for audit.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION,
    analyze_tokens, read_prompts,
)
from run12_encoding_pair_cpu import generation_kwargs
from run12_temperature_pair_cpu import verify_adapter
from run12_token_type_parity import make_inputs

ARMS = ("train_parity", "train_exact")
ROW_FIELDS = frozenset((
    "arm", "prompt_index", "prompt_sha256", "input_token_count",
    "input_token_id_sha256", "output_token_id_sha256",
    "generated_token_count", "eos_position", "stop_reason_inferred",
    "character_count", "distinct_characters",
    "longest_identical_character_run", "punctuation_only",
))


def summarize(rows):
    """Reject incomplete, unpaired or privacy-unsafe experiment records."""
    if len(rows) != 20:
        raise ValueError("Exactly 20 paired rows required")
    paired = {arm: {} for arm in ARMS}
    for row in rows:
        if not isinstance(row, dict) or not set(row).issubset(ROW_FIELDS):
            raise ValueError("Unexpected or privacy-unsafe report field")
        arm, index = row.get("arm"), row.get("prompt_index")
        digest = row.get("prompt_sha256")
        if arm not in paired or type(index) is not int or index not in range(10):
            raise ValueError("Invalid arm or prompt index")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise ValueError("Invalid prompt digest")
        for key in ("input_token_id_sha256", "output_token_id_sha256"):
            value = row.get(key)
            if (not isinstance(value, str) or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)):
                raise ValueError("Invalid token digest")
        if index in paired[arm]:
            raise ValueError("Duplicate prompt index")
        paired[arm][index] = row
    if any(set(group) != set(range(10)) for group in paired.values()):
        raise ValueError("Incomplete paired prompt set")
    if any(paired[ARMS[0]][i]["prompt_sha256"] !=
           paired[ARMS[1]][i]["prompt_sha256"] for i in range(10)):
        raise ValueError("Prompt content differs across arms")
    result = {}
    for arm in ARMS:
        group = list(paired[arm].values())
        result[arm] = {
            "n": len(group),
            "punctuation_only_count": sum(bool(x["punctuation_only"]) for x in group),
            "eos_count": sum(x["stop_reason_inferred"] == "eos" for x in group),
            "max_token_limit_count": sum(
                x["stop_reason_inferred"] == "max_new_tokens" for x in group),
            "max_identical_character_run": max(
                x["longest_identical_character_run"] for x in group),
            "mean_generated_token_count": round(
                sum(x["generated_token_count"] for x in group) / 10, 3),
            "direct_answer_count": None,
            "human_review_required": True,
        }
    result["paired_input_id_differences"] = sum(
        paired[ARMS[0]][i]["input_token_id_sha256"] !=
        paired[ARMS[1]][i]["input_token_id_sha256"] for i in range(10))
    result["paired_output_id_differences"] = sum(
        paired[ARMS[0]][i]["output_token_id_sha256"] !=
        paired[ARMS[1]][i]["output_token_id_sha256"] for i in range(10))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--eval-data", type=Path,
                        default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    adapter_sha = verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=10)
    if len(prompts) != 10:
        parser.error("Exactly ten fixed holdout prompts required")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if torch.cuda.is_available():
        parser.error("CPU-only diagnostic: CUDA is visible")
    torch.set_num_threads(2)
    source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    opts = {"use_fast": True}
    if source == DEFAULT_MODEL:
        opts["revision"] = DEFAULT_REVISION
    tokenizer = AutoTokenizer.from_pretrained(str(source), **opts)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.eos_token_id is None or tokenizer.pad_token_id is None:
        raise ValueError("Missing EOS/PAD token")
    base = AutoModelForCausalLM.from_pretrained(
        DEFAULT_MODEL, revision=DEFAULT_REVISION).to("cpu")
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    model = PeftModel.from_pretrained(
        base, str(args.adapter), is_trainable=False).to("cpu").eval()
    settings = generation_kwargs(tokenizer, 64)
    rows = []
    for index, prompt in enumerate(prompts):
        for arm in ARMS:
            inputs = make_inputs(tokenizer, prompt, arm)
            with torch.inference_mode():
                result = model.generate(**inputs, **settings)
            ids = result[0][inputs["input_ids"].shape[1]:].tolist()
            metrics = analyze_tokens(ids, tokenizer, 64, include_text=False)
            metrics.pop("token_ids", None)
            row = {
                "arm": arm,
                "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "input_token_count": int(inputs["input_ids"].shape[1]),
                "input_token_id_sha256": hashlib.sha256(
                    json.dumps(inputs["input_ids"][0].tolist()).encode()).hexdigest(),
                "output_token_id_sha256": hashlib.sha256(
                    json.dumps(ids).encode()).hexdigest(),
                **metrics,
            }
            rows.append(row)
    summary = summarize(rows)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_gpu_run_id": 39921870784,
        "adapter_sha256": adapter_sha,
        "holdout_sha256": eval_sha,
        "model": DEFAULT_MODEL,
        "model_revision": DEFAULT_REVISION,
        "device": "cpu",
        "gpu_training_performed": False,
        "experiment": "candidate-only greedy train_parity vs train_exact",
        "decode": "greedy; max_new_tokens=64; repetition_penalty=1.12",
        "summary": summary,
        "per_prompt_numeric_diagnostics": rows,
        "promotion_approved": False,
        "interpretation": "Input contract diagnostic only; no semantic or safety approval.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Completed 20 CPU-only paired generations; no raw text or promotion")


if __name__ == "__main__":
    main()
