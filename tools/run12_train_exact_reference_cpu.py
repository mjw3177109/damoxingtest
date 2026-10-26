#!/usr/bin/env python3
"""CPU-only TRAIN-EXACT reference-overlap probe for rejected Run 12 Adapter.

This is a lexical diagnostic, NOT semantic correctness or safety certification.
Exports no prompts, generated text, reference text, or token IDs.
"""
import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION, analyze_tokens, read_prompts,
)
from run12_encoding_pair_cpu import generation_kwargs
from run12_temperature_pair_cpu import verify_adapter
from run12_token_type_parity import make_inputs

ARMS = ("base", "run12_candidate")
ROW_FIELDS = frozenset({
    "arm", "prompt_index", "prompt_sha256", "generated_token_count",
    "eos_position", "stop_reason_inferred", "character_count",
    "distinct_characters", "longest_identical_character_run",
    "punctuation_only", "char_bigram_f1", "output_char_count",
    "cjk_char_count", "empty_output", "reference_char_count",
    "output_to_reference_char_ratio", "short_relative_to_reference",
})


def char_bigram_f1(output, reference):
    """Bounded character bigram overlap: a lexical proxy, not a quality verdict."""
    a = Counter(output[i:i + 2] for i in range(max(0, len(output) - 1)))
    b = Counter(reference[i:i + 2] for i in range(max(0, len(reference) - 1)))
    if not a or not b:
        return 0.0
    common = sum((a & b).values())
    return round(2 * common / (sum(a.values()) + sum(b.values())), 6)


def measure(output, reference):
    return {
        "char_bigram_f1": char_bigram_f1(output, reference),
        "output_char_count": len(output),
        "reference_char_count": len(reference),
        "output_to_reference_char_ratio": round(len(output) / max(1, len(reference)), 3),
        "short_relative_to_reference": len(output) * 4 < len(reference),
        "cjk_char_count": sum("\u4e00" <= c <= "\u9fff" for c in output),
        "punctuation_only": bool(output) and all(
            unicodedata.category(c).startswith("P") for c in output),
        "empty_output": not bool(output.strip()),
    }


def summarize(rows):
    if len(rows) != 20:
        raise ValueError("Expected exactly ten paired prompts per arm")
    groups = {arm: {} for arm in ARMS}
    for row in rows:
        if not isinstance(row, dict) or not set(row).issubset(ROW_FIELDS):
            raise ValueError("Unexpected or privacy-unsafe report field")
        arm, idx, digest = row.get("arm"), row.get("prompt_index"), row.get("prompt_sha256")
        if arm not in groups or type(idx) is not int or idx not in range(10):
            raise ValueError("Invalid arm or prompt index")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest
        ):
            raise ValueError("Invalid prompt provenance")
        if idx in groups[arm]:
            raise ValueError("Duplicate prompt")
        groups[arm][idx] = row
    if any(set(group) != set(range(10)) for group in groups.values()):
        raise ValueError("Missing paired prompts")
    if any(groups[ARMS[0]][i]["prompt_sha256"] !=
           groups[ARMS[1]][i]["prompt_sha256"] for i in range(10)):
        raise ValueError("Unpaired prompt hashes")
    result = {}
    for arm in ARMS:
        rows_arm = list(groups[arm].values())
        result[arm] = {
            "samples": 10,
            "mean_reference_char_bigram_f1": round(
                sum(r["char_bigram_f1"] for r in rows_arm) / 10, 6),
            "nonempty_count": sum(not r["empty_output"] for r in rows_arm),
            "cjk_present_count": sum(r["cjk_char_count"] > 0 for r in rows_arm),
            "punctuation_only_count": sum(r["punctuation_only"] for r in rows_arm),
            "eos_count": sum(r["stop_reason_inferred"] == "eos" for r in rows_arm),
            "short_relative_to_reference_count": sum(r["short_relative_to_reference"] for r in rows_arm),
            "eos_and_short_count": sum(
                r["short_relative_to_reference"] and r["stop_reason_inferred"] == "eos"
                for r in rows_arm
            ),
            "eos_and_short_indices": sorted(
                r["prompt_index"] for r in rows_arm
                if r["short_relative_to_reference"] and r["stop_reason_inferred"] == "eos"
            ),
            "mean_output_to_reference_char_ratio": round(
                sum(r["output_to_reference_char_ratio"] for r in rows_arm) / 10, 3),
            "mean_generated_token_count": round(
                sum(r["generated_token_count"] for r in rows_arm) / 10, 3),
            "direct_answer_count": None,
            "human_review_required": True,
        }
    result["candidate_minus_base_bigram_f1"] = round(
        result["run12_candidate"]["mean_reference_char_bigram_f1"] -
        result["base"]["mean_reference_char_bigram_f1"], 6)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    adapter_sha = verify_adapter(args.adapter)
    prompts, eval_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=10)
    references = [
        json.loads(line)["response"] for line in
        args.eval_data.read_text(encoding="utf-8").splitlines() if line.strip()
    ][:10]
    if len(prompts) != 10 or len(references) != 10 or any(
        not isinstance(ref, str) or not ref.strip() for ref in references
    ):
        raise ValueError("Expected ten fixed prompts and nonempty references")

    import torch
    if torch.cuda.is_available():
        raise RuntimeError("CPU-only experiment: CUDA device visible")
    torch.set_num_threads(2)
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer_source = args.adapter if (args.adapter / "tokenizer_config.json").exists() else DEFAULT_MODEL
    opts = {"use_fast": True}
    if tokenizer_source == DEFAULT_MODEL:
        opts["revision"] = DEFAULT_REVISION
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_source), **opts)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if tokenizer.pad_token_id is None or tokenizer.eos_token_id is None:
        raise ValueError("PAD/EOS missing")
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).to("cpu")
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise ValueError("Tokenizer/model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    base.eval()
    settings = generation_kwargs(tokenizer)
    rows = []

    def evaluate(model, arm):
        model.eval()
        for idx, (prompt, reference) in enumerate(zip(prompts, references)):
            inputs = make_inputs(tokenizer, prompt, "train_exact")
            with torch.inference_mode():
                generated = model.generate(**inputs, **settings)
            ids = generated[0][inputs["input_ids"].shape[1]:].tolist()
            diag = analyze_tokens(ids, tokenizer, 64)
            diag.pop("token_ids", None)
            output = tokenizer.decode(ids, skip_special_tokens=True).strip()
            rows.append({
                "arm": arm, "prompt_index": idx,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                **diag, **measure(output, reference),
            })

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False).to("cpu")
    evaluate(candidate, "run12_candidate")
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_gpu_run_id": "39921870784",
        "adapter_sha256": adapter_sha, "holdout_sha256": eval_sha,
        "model": DEFAULT_MODEL, "model_revision": DEFAULT_REVISION,
        "device": "cpu", "decoding": "greedy",
        "input_contract": "train_exact (no automatic special tokens or token_type_ids)",
        "gpu_training_performed": False, "quality_certified": False,
        "summary": summarize(rows), "per_prompt_numeric_diagnostics": rows,
        "promotion_approved": False,
        "interpretation": "TRAIN-EXACT lexical/length proxies only; no semantic or safety certification.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Completed 20 TRAIN-EXACT CPU-only generations; numeric-only report; no promotion")


if __name__ == "__main__":
    main()
