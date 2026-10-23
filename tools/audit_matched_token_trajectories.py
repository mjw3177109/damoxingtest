#!/usr/bin/env python3
"""Compare token probabilities only while base/candidate generated histories match.

Pure offline audit of an existing CPU Artifact; never loads a model or prompts.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

EXPECTED_SOURCE_RUN = "39921870784"
EXPECTED_HOLDOUT_SHA256 = "5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f"
EXPECTED_ADAPTER_SHA256 = "979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c"


def compare(data):
    """Produce a small evidence-only summary, avoiding invalid cross-history comparisons."""
    if (str(data.get("source_training_run_id")) != EXPECTED_SOURCE_RUN
            or data.get("holdout_sha256") != EXPECTED_HOLDOUT_SHA256
            or data.get("adapter_weights_sha256") != EXPECTED_ADAPTER_SHA256
            or data.get("first_step_parity") != "matched audited Run 39975111441 on all 4 prompts and both models"):
        raise ValueError("Wrong or unverified Run 12 evidence")
    results = data.get("results")
    if not isinstance(results, list) or len(results) != 8:
        raise ValueError("Expected 4 prompts x 2 phases")
    grouped = {}
    for result in results:
        key = (result.get("prompt_index"), result.get("phase"))
        if key in grouped or key[0] not in range(4) or key[1] not in ("base", "candidate"):
            raise ValueError("Duplicate or unexpected phase/prompt")
        rows = result.get("rows")
        ids = result.get("selected_token_ids")
        if not isinstance(rows, list) or not isinstance(ids, list) or len(rows) != len(ids) or not 1 <= len(ids) <= 8:
            raise ValueError("Invalid trace length")
        for i, row in enumerate(rows):
            p = row.get("watch_probabilities", {}).get("119")
            if (row.get("step") != i + 1 or row.get("selected_token_id") != ids[i]
                    or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1):
                raise ValueError("Malformed probability trace")
        grouped[key] = result
    comparisons = []
    comparable_count = 0
    positive = negative = unchanged = 0
    for index in range(4):
        base = grouped[index, "base"]
        candidate = grouped[index, "candidate"]
        if base.get("prompt_sha256") != candidate.get("prompt_sha256"):
            raise ValueError("Prompt hashes do not match")
        deltas = []
        for step, (brow, crow) in enumerate(zip(base["rows"], candidate["rows"])):
            if base["selected_token_ids"][:step] != candidate["selected_token_ids"][:step]:
                break
            delta = crow["watch_probabilities"]["119"] - brow["watch_probabilities"]["119"]
            deltas.append(round(delta, 9))
            comparable_count += 1
            if delta > 0:
                positive += 1
            elif delta < 0:
                negative += 1
            else:
                unchanged += 1
        comparisons.append({
            "prompt_index": index,
            "matched_history_steps": len(deltas),
            "token_119_probability_deltas_candidate_minus_base": deltas,
            "first_divergence_after_step": next((i + 1 for i, (a, b) in enumerate(zip(base["selected_token_ids"], candidate["selected_token_ids"])) if a != b), None),
        })
    return {
        "audit_type": "matched_history_token_119_probability_posthoc",
        "source_training_run_id": EXPECTED_SOURCE_RUN,
        "source_cpu_run_id": "39984106556",
        "holdout_sha256": EXPECTED_HOLDOUT_SHA256,
        "adapter_weights_sha256": EXPECTED_ADAPTER_SHA256,
        "gpu_training_performed": False,
        "new_model_forward_passes": 0,
        "source_model_forward_passes": data.get("model_forward_passes"),
        "matched_history_comparisons": comparable_count,
        "positive_deltas": positive,
        "negative_deltas": negative,
        "zero_deltas": unchanged,
        "prompts": comparisons,
        "model_promotion_approved": False,
        "interpretation": "Probability differences are comparable only while both models share the same prompt and generated-token prefix. Later steps after divergent tokens are not controlled comparisons. Neither signs of probability deltas nor repetition alone prove a causal root cause or quality gain.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha256", required=True, help="Expected raw JSON SHA-256")
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.sha256:
        parser.error("Input evidence SHA-256 mismatch")
    summary = compare(json.loads(raw))
    summary["source_artifact_json_sha256"] = args.sha256
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Audited", summary["matched_history_comparisons"], "controlled comparisons; no new inference or training")


if __name__ == "__main__":
    main()
