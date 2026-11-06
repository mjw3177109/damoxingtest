# GPT-2 T4 | Existing Kaggle Kernel provenance and offline status matrix | 2026-10-26 05:00 Asia/Shanghai

## Hypothesis and root cause
The previous Daily workflow, on detecting an already RUNNING/QUEUED/PENDING canonical Kaggle Kernel, monitored it and later downloaded its outputs into the **new** GitHub Actions Run directory. The current workflow did not verify whether the pre-existing Kernel belonged to that GitHub Run or was manually submitted. This is a code-path provenance risk, not evidence that a specific past run was misattributed.

## Minimal repair (Draft PR #70; NOT merged)
- `.github/workflows/daily-gpt2-training.yml`: when an existing remote Kernel is active, write `BLOCKED_EXISTING_KERNEL_ACTIVE` and exit without pushing, downloading or attributing its outputs to the current run. The active remote task is not cancelled or modified.
- `scripts/finalize_report.py`: explain that this run did not submit new training and that the existing Kernel's Run/Kernel ID, code SHA, data SHA, metrics and artifacts require separate provenance review.
- `tests/test_blocked_retrain_report.py`: add regression for honest active-kernel report semantics.
- `tests/test_kaggle_kernel_status_matrix.py`: execute the actual workflow Bash step against a local fake Kaggle CLI and no-op sleep. Scenarios: RUNNING, QUEUED, FAILED, FAILED+explicit manual approval, UNKNOWN, UNAUTHORIZED, COMPLETE and 404-missing. The fake CLI cannot access the network or GPU.
- Existing `approve_same_data_retrain` and `approve_failed_kernel_retry` constraints, concurrency lock, quality gate and rollback policy remain unchanged. No secrets, model weights, training data or architecture modified.

## Validation and evidence
- Main baseline SHA: `1237531d03cb3d43837e76da21d2a00b5d19cc24`.
- Tested candidate SHA: `226b980295f8db8a12bd514d8a52673e9b797a19`.
- CI: https://github.com/mjw3177109/damoxingtest/actions/runs/40233957170 — completed/success, **201/201 tests**, Ruff F821 pass, response-only collator and -100 mask pass. Job `121291415973` inspected.
- Intermediate test fixture `98d581f99f13a8cea4798e31c6605c1e166ba2c2` failed CI `40233923475` due to a literal escaped newline; fixed in `a0f1d95535db2b381c464df141be3763d71bc42b`, verified by passing CI. Do not claim the failed intermediate version passed.
- Fake-CLI status matrix passed: existing RUNNING/QUEUED, FAILED, UNKNOWN and UNAUTHORIZED resulted in **zero pushes**; reviewed FAILED retry, existing COMPLETE and 404-missing reached one mocked submission. The latter cases are gated by the upstream same-data approval guard in the real workflow. This is an **offline simulation only**, not a live Kaggle test.
- Latest Daily: `40165941479` completed/success but `SKIPPED_NO_CHANGES`, `kaggle_kernel_submitted=false`. Artifact `12588187512` exists and is not expired.
- Historical GPU training: `39921870784`, completed; Artifact `12487687305` exists and is not expired. No new GPU submission was performed in this audit.
- Kaggle real-time Kernel status, quota and manual runs: **not independently verified**.

## Historical model evidence (not current measurements)
- Training SHA256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`.
- Evaluation SHA256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Base model revision: `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- GPU Tesla T4, 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599.
- Generation example: `................................................................`; historical meaningful sample count 0/10; human review pending; `promotion_approved=false`.
- Run 8 vs Run 12 used different validation sets; no comparable cross-run historical-best claim. No new model metrics, generation, or promotion.

## Decision, lessons and next steps
- Decision: **Draft PR #70 remains unmerged; no Kaggle GPU training; candidate model promotion rejected**.
- Lesson: a pre-existing active remote job is not proof that the current GitHub Actions Run trained a model. Prevent duplicate pushes and false provenance attribution; keep remote jobs untouched.
- Next: verify actual remote Kernel ID, owner, code/data provenance and quota with authorized Kaggle access; audit manual/scheduled dispatch paths and approved checkpoint rollback; then decide whether to merge PR #70. If a new GPU experiment is justified, specify one measurable hypothesis and compare against a common fixed holdout with a rollback point.
- The old `DataCollatorForLanguageModeling` NameError is absent from main; `response_only_collator` remains in the Trainer path. No redundant fix.
- Protect users and humanity; never log or commit credentials or personal information; do not bypass safety controls.
