#!/usr/bin/env python3
"""Bounded CPU-only Run 12 base/candidate readability evidence (no training)."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from generation_decode_probe import (
    DEFAULT_EVAL_SHA256, DEFAULT_MODEL, DEFAULT_REVISION,
    analyze_tokens, read_prompts,
)
from run12_token_type_parity import make_inputs

SENSITIVE = re.compile(
    r"(?i)(?:https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[a-z]{2,}"
    r"|\b(?:\+?\d[\d\s().-]{9,}\d)\b|\b(?:sk|ghp|gho|github_pat)-[\w-]{8,}\b)"
)


def safe_excerpt(text, limit=160):
    """Fail closed on possible contact information or credentials."""
    if not isinstance(text, str):
        raise TypeError("Generated output must be text")
    if SENSITIVE.search(text):
        return "[REDACTED: possible sensitive content]"
    clean = "".join(ch for ch in text if ch.isprintable()).strip()
    return clean[:limit] + ("…" if len(clean) > limit else "")



def diagnose_decode_visibility(token_ids, tokenizer):
    """Classify a blank generation without exporting raw tokens or unredacted text.

    A nonempty token sequence can decode to empty text because it consists of
    special tokens, or to whitespace that is removed by .strip().  The two
    cases need different follow-up tests and must not be conflated.
    """
    ids = [int(value) for value in token_ids]
    special_ids = set(getattr(tokenizer, "all_special_ids", []) or [])
    eos_id = getattr(tokenizer, "eos_token_id", None)
    pad_id = getattr(tokenizer, "pad_token_id", None)
    unfiltered = tokenizer.decode(ids, skip_special_tokens=False)
    filtered = tokenizer.decode(ids, skip_special_tokens=True)
    stripped = filtered.strip()
    if stripped:
        category = "visible_text"
    elif filtered:
        category = "whitespace_only" if filtered.isspace() else "stripped_invisible"
    elif ids and all(value in special_ids for value in ids):
        category = "special_tokens_only"
    elif ids:
        category = "decoder_filtered_all"
    else:
        category = "no_generated_tokens"
    return {
        "category": category,
        "token_count": len(ids),
        "special_token_count": sum(value in special_ids for value in ids),
        "eos_token_count": sum(value == eos_id for value in ids) if eos_id is not None else 0,
        "pad_token_count": sum(value == pad_id for value in ids) if pad_id is not None else 0,
        "unfiltered_decode_length": len(unfiltered),
        "filtered_decode_length": len(filtered),
        "stripped_decode_length": len(stripped),
        "filtered_whitespace_count": sum(char.isspace() for char in filtered),
        "filtered_nonprintable_count": sum(not char.isprintable() for char in filtered),
    }


def summarize(rows):
    expected = {(phase, i) for phase in ("base", "candidate") for i in range(4)}
    keys = [(r["phase"], r["prompt_index"]) for r in rows]
    if len(keys) != 8 or len(set(keys)) != 8 or set(keys) != expected:
        raise ValueError("Expected exactly eight unique base/candidate paired generations")
    return {phase: {
        "count": 4,
        "punctuation_only": sum(bool(r["punctuation_only"]) for r in rows if r["phase"] == phase),
        "contains_chinese": sum(bool(re.search(r"[\u3400-\u9fff]", r["safe_output_excerpt"]))
                                for r in rows if r["phase"] == phase),
        "eos": sum(r["stop_reason_inferred"] == "eos" for r in rows if r["phase"] == phase),
        "manual_review_required": True,
    } for phase in ("base", "candidate")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--eval-data", type=Path, default=Path("data/safety_humanity_eval_v1.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.adapter / "adapter_config.json").is_file():
        parser.error("Pinned Run 12 Adapter missing; refusing fallback")
    prompts, eval_sha = read_prompts(args.eval_data, DEFAULT_EVAL_SHA256, limit=4)

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(2)
    source = args.adapter if (args.adapter / "tokenizer_config.json").is_file() else DEFAULT_MODEL
    tokenizer = AutoTokenizer.from_pretrained(str(source), use_fast=True)
    if tokenizer.eos_token is None and tokenizer.sep_token is not None:
        tokenizer.eos_token = tokenizer.sep_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(DEFAULT_MODEL, revision=DEFAULT_REVISION).cpu().eval()
    if base.get_input_embeddings().num_embeddings != len(tokenizer):
        raise RuntimeError("Tokenizer and base model vocabulary mismatch")
    base.config.pad_token_id = tokenizer.pad_token_id
    rows = []

    def evaluate(model, phase):
        model.eval()
        for index, prompt in enumerate(prompts):
            inputs = make_inputs(tokenizer, prompt, "train_parity")
            torch.manual_seed(42 + index)
            with torch.inference_mode():
                generated = model.generate(
                    **inputs, max_new_tokens=64, do_sample=False,
                    repetition_penalty=1.12,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            ids = generated[0][inputs["input_ids"].shape[1]:].tolist()
            diagnostics = analyze_tokens(ids, tokenizer, 64, include_text=True)
            output = diagnostics.pop("output")
            diagnostics.pop("token_ids")  # Prevent reconstructing unsanitized text.
            rows.append({
                "phase": phase, "prompt_index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "safe_output_excerpt": safe_excerpt(output),
                "decode_visibility": diagnose_decode_visibility(ids, tokenizer),
                **diagnostics,
            })

    evaluate(base, "base")
    candidate = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False)
    evaluate(candidate, "candidate")
    summary = summarize(rows)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_training_run_id": 39921870784,
        "model_revision": DEFAULT_REVISION,
        "holdout_sha256": eval_sha,
        "device": "cpu",
        "experiment": "base vs rejected LoRA candidate, same four prompts and train-parity inputs",
        "generations": 8,
        "summary": summary,
        "results": rows,
        "quality_certified": False,
        "promotion_approved": False,
        "gpu_training_performed": False,
        "note": "Excerpts are privacy-filtered; human evaluation of relevance, accuracy and safety remains required.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
