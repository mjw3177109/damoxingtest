# 2026-10-24 | Pre-submit Kaggle duplicate prevention (PR #40)

## Problem and evidence
- Historical real GPU training: GitHub Actions Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), 2026-10-23; 33 optimizer steps on Tesla T4 (14.56 GiB).
- Later Daily Run [40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092), 2026-10-24, reported `SKIPPED_NO_CHANGES` and 0 optimizer steps but still submitted a new Kaggle kernel version. Its checked-in `kaggle_initial_status.log` and `kaggle_status.log` show COMPLETE before submission and QUEUED→COMPLETE after.
- Root cause: duplicate-data/recipe detection was performed inside the Kaggle notebook **after** the GitHub workflow had already pushed the kernel.
- Prior candidate quality gate: 0/10 meaningful generated samples, `promotion_approved=false`; no verified model improvement.

## Small fix and validation
- [PR #40](https://github.com/mjw3177109/damoxingtest/pull/40), merged as commit `00ca40efcfb96a9c9532182dd1bd14c77affda8c`.
- Added `tools/pre_submit_reuse_guard.py` and `tests/test_pre_submit_reuse_guard.py`; modified only `.github/workflows/daily-gpt2-training.yml` to skip Kaggle installation, metadata preparation, and kernel submission when a matching completed data/recipe run is found.
- The guard reuses the existing training hash contract, writes `PRE_SUBMIT_SKIPPED_NO_CHANGES`, sets current training steps to 0, GPU to null, and explicitly labels metrics/samples as historical. The quality gate remains active and rejects skipped candidates.
- Four new offline regression tests cover historical provenance, no-GPU claims, incomplete/skipped sources, and missing hashes/samples.
- [Static preflight Run 40080220044](https://github.com/mjw3177109/damoxingtest/actions/runs/40080220044): `completed/success` on PR head `f6025bed5970a82a5d954f9a4949c447750bb8a3`.
- No Kaggle kernel was submitted as part of this PR. No training script, data, model weights, credentials, or quality threshold changed.

## Training configuration and comparison
- Fixed model: `uer/gpt2-chinese-cluecorpussmall`, revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Training data SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; fixed holdout SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Historical Run 12: 3 epochs, learning rate 0.0002, LoRA rank 8, train loss 3.246455, validation loss 3.147277, PPL 23.272599.
- No new GPU steps, Train Loss, Val Loss, PPL, or new model answers in this fix. Historical Run 8 used a different validation set and cannot establish cross-run superiority.
- Previous rejected adapter and approved checkpoints remain unchanged. Model promotion: **rejected**.

## Limits and next evidence
1. CI proves the new unit/static contracts, **not** an end-to-end scheduled Kaggle execution. On the next Daily run, verify that no new kernel version was submitted and that report, quality gate, and Artifact all show pre-submit skip.
2. Kaggle real-time status was not independently available; last observed COMPLETE comes from the checked-in 2026-10-24 Actions logs.
3. For model quality, pre-register one tokenization-changing prompt variant, verify actual token IDs before CPU comparison, and keep generation-quality checks separate from infrastructure success.
4. If any guard failure occurs, investigate the actual log, perform a minimal fix, rerun tests, and do not spend GPU quota until safe.

## Experience
Move duplicate-work detection **before** the costly remote action. Keep current-run evidence separate from historical evidence. A successful Actions run or completed Kaggle kernel does not prove a new model was trained, improved, or promoted. Never expose tokens, secrets, or private data.
