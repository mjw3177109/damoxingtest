#!/usr/bin/env python3
"""Audit Trainer gradient-norm log entries without exposing raw training logs.

Reported Trainer grad_norm values are usually measured before gradient clipping;
large values alone do not prove clipping was bypassed or training was unstable.
"""
import argparse
import ast
import hashlib
import json
import math
import re
from pathlib import Path

METRIC_LINE = re.compile(r"Trainer metrics at step\s+(\d+):\s+(\{[^\n]*\})")


def audit_log(raw, max_grad_norm=1.0):
    if not isinstance(raw, str):
        raise ValueError("Training log must be UTF-8 text")
    if not math.isfinite(max_grad_norm) or max_grad_norm <= 0:
        raise ValueError("max_grad_norm must be finite and positive")
    records = []
    for match in METRIC_LINE.finditer(raw):
        try:
            item = ast.literal_eval(match.group(2))
        except (ValueError, SyntaxError, TypeError, RecursionError) as exc:
            raise ValueError("Malformed Trainer metrics record") from exc
        if not isinstance(item, dict):
            raise ValueError("Trainer metrics record must be a dictionary")
        if "grad_norm" not in item:
            continue
        norm = item["grad_norm"]
        if isinstance(norm, bool) or not isinstance(norm, (int, float)):
            raise ValueError("Non-numeric gradient norm")
        if not math.isfinite(norm) or norm < 0:
            raise ValueError("Non-finite or negative gradient norm")
        records.append((int(match.group(1)), float(norm)))
    if not records:
        raise ValueError("No actual Trainer gradient-norm records found")
    if any(a[0] >= b[0] for a, b in zip(records, records[1:])):
        raise ValueError("Gradient-norm steps are not strictly increasing")
    norms = [value for _, value in records]
    return {
        "training_log_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "gradient_record_count": len(records),
        "first_step": records[0][0],
        "last_step": records[-1][0],
        "min_logged_grad_norm": min(norms),
        "max_logged_grad_norm": max(norms),
        "first_logged_grad_norm": norms[0],
        "last_logged_grad_norm": norms[-1],
        "count_above_configured_max_grad_norm": sum(x > max_grad_norm for x in norms),
        "configured_max_grad_norm": max_grad_norm,
        "interpretation": (
            "These are logged gradient norms, generally before clipping; "
            "values above max_grad_norm do not prove that clipping failed. "
            "The log alone cannot identify a causal mechanism for poor generation."
        ),
        "promotion_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    args = parser.parse_args()
    raw = args.training_log.read_text(encoding="utf-8")
    result = audit_log(raw, args.max_grad_norm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Audited", result["gradient_record_count"], "gradient records (no training performed)")


if __name__ == "__main__":
    main()
