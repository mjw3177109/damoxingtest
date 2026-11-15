#!/usr/bin/env python3
"""Skip duplicate Kaggle submissions before the remote kernel is pushed.

Uses the existing training-recipe/data hash contract. Never starts a model,
reads credentials, changes checkpoints, or treats reused metrics as new.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from train_gpt2_lora import find_reusable_run  # noqa: E402
from inference_only_submission_hold import should_hold_inference_only  # noqa: E402

REQUIRED = ("metrics.json", "samples.json", "run_metadata.json", "summary.md")


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
    args = parser.parse_args()
    candidate = find_reusable_run(SimpleNamespace(
        data=args.data, eval_data=args.eval_data, force_retrain=False
    ))
    reuse = candidate is not None
    hold = False
    if reuse:
        source = materialize_skip(candidate["run_dir"], args.run_dir)
        print("SKIPPED_NO_CHANGES before Kaggle submission; historical source:", source)
    elif should_hold_inference_only(ROOT):
        # Exact audited inference-only change: do not submit a new GPU job
        # merely because the whole-file training recipe hash changed.
        # Do not reuse old evaluation metrics as fresh inference results.
        hold = True
        args.run_dir.mkdir(parents=True, exist_ok=True)
        target = args.run_dir / "kaggle_output" / "training_output"
        target.mkdir(parents=True, exist_ok=True)
        (args.run_dir / "status.txt").write_text(
            "BLOCKED_INFERENCE_ONLY_CHANGE\n", encoding="utf-8"
        )
        write_json(target / "training_status.json", {
            "status": "blocked",
            "reason": "audited_inference_only_change",
            "kaggle_kernel_submitted": False,
            "current_run_performed_gpu_training": False,
            "message": "Exact audited inference-only edit; no Kaggle submission or new evaluation.",
        })
        (target / "training.log").write_text(
            "BLOCKED_INFERENCE_ONLY_CHANGE; no Kaggle submission, "
            "GPU training, new metrics or generation.\n", encoding="utf-8"
        )
        print("BLOCKED_INFERENCE_ONLY_CHANGE; no GPU submission authorized.")
    else:
        print("No completed matching data/recipe evidence; normal guarded Kaggle path applies.")
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write("reuse=" + ("true" if reuse else "false") + "\n")
        handle.write("hold=" + ("true" if hold else "false") + "\n")


if __name__ == "__main__":
    main()
