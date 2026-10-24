#!/usr/bin/env python3
"""Read-only aggregate audit of Trainer gradient-norm log entries.

No model, GPU, Kaggle submission, or raw log publishing. Logged norms can be
pre-clipping: large values alone do not establish clipping failure.
"""
import argparse
import json
import math
import re
import statistics
from pathlib import Path

STEP = re.compile(r"Trainer metrics at step\s+(\d+):")
NORM = re.compile(r"['\"]grad_norm['\"]\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?nan|[-+]?inf)", re.I)


def audit_log(content, max_grad_norm=1.0):
    if not math.isfinite(max_grad_norm) or max_grad_norm <= 0:
        raise ValueError("max_grad_norm must be positive and finite")
    readings = []
    for line in content.splitlines():
        if "Trainer metrics at step" not in line or "grad_norm" not in line:
            continue
        step = STEP.search(line)
        norm = NORM.search(line)
        if not step or not norm:
            raise ValueError("Unparseable Trainer gradient-norm entry")
        readings.append((int(step.group(1)), float(norm.group(1))))
    if not readings:
        raise ValueError("No Trainer gradient-norm entries found")
    finite = [norm for _, norm in readings if math.isfinite(norm)]
    nonfinite_steps = [step for step, norm in readings if not math.isfinite(norm)]
    return {
        "gradient_norm_observations": len(readings),
        "observed_steps": [step for step, _ in readings],
        "nonfinite_gradient_steps": nonfinite_steps,
        "max_grad_norm_config": max_grad_norm,
        "logged_norm_above_threshold_count": sum(norm > max_grad_norm for norm in finite),
        "logged_norm_min": min(finite) if finite else None,
        "logged_norm_median": statistics.median(finite) if finite else None,
        "logged_norm_max": max(finite) if finite else None,
        "interpretation": "Logged gradient norms may be measured before clipping. Values above max_grad_norm do not establish clipping failure or a training root cause.",
        "training_performed_by_audit": False,
        "promotion_approved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("training_log", type=Path)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_log(args.training_log.read_text(encoding="utf-8"), args.max_grad_norm)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
