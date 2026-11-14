#!/usr/bin/env python3
"""Skip duplicate Kaggle submissions before the remote kernel is pushed.

Uses the existing training-recipe/data hash contract. Never starts a model,
reads credentials, changes checkpoints, or treats reused metrics as new.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from train_gpt2_lora import find_reusable_run  # noqa: E402

REQUIRED = ("metrics.json", "samples.json", "run_metadata.json", "summary.md")


def has_completed_same_data_run(data, eval_data, repo_root=ROOT):
    """Find historical GPU evidence for the same data without trusting recipe reuse.

    A script-only guard fix changes the legacy whole-file recipe hash. In that
    case a failed exact reuse check must NOT silently authorize a new GPU run.
    This conservative check is read-only; approval is separate from promotion.
    """
    root = Path(repo_root).resolve()
    train = Path(data)
    holdout = Path(eval_data)
    train = train if train.is_absolute() else root / train
    holdout = holdout if holdout.is_absolute() else root / holdout
    if not train.is_file() or not holdout.is_file():
        return False
    train_sha = hashlib.sha256(train.read_bytes()).hexdigest()
    eval_sha = hashlib.sha256(holdout.read_bytes()).hexdigest()
    for path in sorted(root.glob("reports/*/run-*/run_metadata.json"), reverse=True):
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            if (metadata.get("training_data_sha256") != train_sha
                    or metadata.get("eval_data_sha256") != eval_sha):
                continue
            status = json.loads((path.parent / "training_status.json").read_text(encoding="utf-8"))
            if status.get("status") == "completed" and not status.get("skipped_no_changes"):
                return True
        except (OSError, ValueError, TypeError):
            continue
    return False


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def materialize_skip(source, run_dir, repo_root=ROOT):
    """Produce auditable, explicitly historical evidence without Kaggle/GPU."""
    source, run_dir = Path(source), Path(run_dir)
    for name in REQUIRED + ("training_status.json",):
        if not (source / name).is_file():
            raise ValueError("Reusable source is missing " + name)
    status = json.loads((source / "training_status.json").read_text(encoding="utf-8"))
    if status.get("status") != "completed" or status.get("skipped_no_changes"):
        raise ValueError("Only a real completed training source may be reused")
    metrics = json.loads((source / "metrics.json").read_text(encoding="utf-8"))
    samples = json.loads((source / "samples.json").read_text(encoding="utf-8"))
    metadata = json.loads((source / "run_metadata.json").read_text(encoding="utf-8"))
    if not isinstance(samples, list) or len(samples) < 10:
        raise ValueError("Reusable source lacks fixed evaluation samples")
    if not metrics.get("training_data_sha256") or not metrics.get("eval_data_sha256"):
        raise ValueError("Reusable source lacks data provenance")
    origin = str(source.resolve().relative_to(Path(repo_root).resolve()))
    now = datetime.now(timezone.utc).isoformat()
    target = run_dir / "kaggle_output" / "training_output"
    target.mkdir(parents=True, exist_ok=True)
    metrics.update({
        "training_skipped": True, "current_run_performed_gpu_training": False,
        "reused_from_run": origin, "train_steps": 0, "train_loss": None,
        "gpu_name": None, "gpu_memory_gib": None,
        "interpretation": "PRE-SUBMISSION SKIP: no Kaggle kernel was submitted. "
                          "All evaluation metrics and samples are historical from " + origin + ".",
    })
    metadata.update({
        "source_run_started_at_utc": metadata.get("started_at_utc"),
        "started_at_utc": now,
        "source_run_gpu_name": metadata.get("gpu_name"),
        "source_run_gpu_memory_gib": metadata.get("gpu_memory_gib"),
        "source_run_cuda_available": metadata.get("cuda_available"),
        "gpu_name": None, "gpu_memory_gib": None, "cuda_available": False,
        "training_skipped": True, "current_run_performed_gpu_training": False,
        "kaggle_kernel_submitted": False, "reused_from_run": origin,
    })
    write_json(target / "metrics.json", metrics)
    write_json(target / "samples.json", samples)
    write_json(target / "run_metadata.json", metadata)
    write_json(target / "training_status.json", {
        "status": "completed", "skipped_no_changes": True,
        "kaggle_kernel_submitted": False, "finished_at_utc": now,
        "reused_from_run": origin,
        "message": "Skipped before Kaggle submission; no training or evaluation performed.",
    })
    (target / "summary.md").write_text(
        "No new training: Kaggle kernel submission skipped. Historical evidence: "
        + origin + ".\n", encoding="utf-8"
    )
    (target / "training.log").write_text(
        now + " | INFO | PRE_SUBMIT_SKIPPED_NO_CHANGES; "
        "no Kaggle submission, GPU training, or new evaluation.\n", encoding="utf-8"
    )
    (run_dir / "status.txt").write_text("PRE_SUBMIT_SKIPPED_NO_CHANGES\n", encoding="utf-8")
    return origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/safety_humanity_train_v2.jsonl")
    parser.add_argument("--eval-data", default="data/safety_humanity_eval_v1.jsonl")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--approve-same-data-retrain", action="store_true",
                        help="Explicit workflow_dispatch approval after reviewing changed recipe")
    args = parser.parse_args()
    # An explicit manual retrain approval must not silently reuse an exact
    # historical match. The workflow still performs its remote Kaggle checks.
    candidate = None if args.approve_same_data_retrain else find_reusable_run(
        SimpleNamespace(data=args.data, eval_data=args.eval_data, force_retrain=False)
    )
    reuse = candidate is not None
    blocked = (not reuse and not args.approve_same_data_retrain
               and has_completed_same_data_run(args.data, args.eval_data))
    if reuse:
        source = materialize_skip(candidate["run_dir"], args.run_dir)
        print("SKIPPED_NO_CHANGES before Kaggle submission; historical source:", source)
    elif blocked:
        args.run_dir.mkdir(parents=True, exist_ok=True)
        (args.run_dir / "status.txt").write_text(
            "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL\n", encoding="utf-8"
        )
        write_json(args.run_dir / "reuse_guard_decision.json", {
            "decision": "blocked",
            "reason": "Same-data completed training exists but exact recipe/config reuse failed.",
            "kaggle_kernel_submitted": False,
            "approval_required": "workflow_dispatch approve_same_data_retrain",
        })
        print("BLOCKED: same-data retrain needs explicit approval; no Kaggle submission.")
    else:
        print("No reusable evidence or explicit approval; normal guarded Kaggle path applies.")
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write("reuse=" + ("true" if reuse else "false") + "\n")
        handle.write("blocked=" + ("true" if blocked else "false") + "\n")


if __name__ == "__main__":
    main()
