# GPT-2 T4 | Terminal-failure Kaggle retry guard | 2026-10-26 04:00 Asia/Shanghai

## Scope and hypothesis
A previously failed Kaggle Kernel was automatically re-submitted on the next eligible Daily run. If no completed same-data evidence exists, the normal pre-submit reuse guard cannot prevent repeated failed GPU attempts. Hypothesis: the `ERROR/FAILED/CANCELLED` branch in the canonical workflow's initial status check authorizes a push without an explicit retry review.

## Verified root cause
Before this change, `.github/workflows/daily-gpt2-training.yml` set `NEED_PUSH=true` for terminal `ERROR/FAILED/CANCELLED` remote states. This is a code-path risk, **not** evidence of a new failed Kaggle run. The prior same-data approval gate addresses completed historical training and is not sufficient for failed remote kernels with no completed source.

## Minimal changes (Draft PR #70; not merged)
- Added optional `workflow_dispatch` input `approve_failed_kernel_retry`, default `false`.
- Only a manually dispatched event can populate the retry-approval environment variable.
- On an existing remote `ERROR/FAILED/CANCELLED`, default to `BLOCKED_FAILED_KERNEL_REQUIRES_APPROVAL`, write `status.txt`, and exit before `kaggle kernels push`.
- A reviewed manual approval allows **one workflow submission attempt** through the existing status, concurrency, and artifact checks. If same-data completed evidence also exists, the separate `approve_same_data_retrain` requirement still applies.
- Updated `scripts/finalize_report.py` to distinguish a deliberate failed-kernel retry block from a new GPU failure, and added two offline regression tests.
- No model architecture, data, optimizer, GPU quota, promotion gate, secrets, or checkpoint changes.

## Auditable evidence
- Baseline main SHA: `1237531d03cb3d43837e76da21d2a00b5d19cc24`.
- Validated candidate SHA: `6f89d6d596b5731873cbed7362170fe3b05d8a51`.
- Static Preflight Run: `40228675443` — completed/success, 195/195 tests, Ruff F821 pass; https://github.com/mjw3177109/damoxingtest/actions/runs/40228675443
- An intermediate test-fixture commit `2ff568fb64c0a813f75c6b972ed84ac30e1a6d3b` failed CI Run `40228658491` because the fixture accidentally wrote a literal `\\n`; corrected in `6f89d6d596b5731873cbed7362170fe3b05d8a51`, which passed CI. No GPU involved.
- Existing latest Daily Training Run: `40165941479` — completed/success but `SKIPPED_NO_CHANGES`, `kaggle_kernel_submitted=false`; source `reports/2026-10-23/run-39921870784`.
- Latest Daily Artifact `12588187512`; historical Run 12 Artifact `12487687305` (both present and not expired at audit time).
- Kaggle real-time Kernel state and remaining GPU quota: **not independently verified**; no Kaggle CLI or GPU job executed in this audit.

## Historical training evidence (not new measurements)
- Source Run `39921870784`, GPU NVIDIA Tesla T4, 14.56 GiB; 3 epochs, 33 steps; Train Loss 3.246455; Val Loss 3.147277; PPL 23.272599.
- Train data SHA256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; eval data SHA256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Model revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`; historical generation includes `................................................................`; automated quality gate 0/10 meaningful samples, independent human review pending, `promotion_approved=false`.
- No new Train/Val Loss, PPL, training steps, model weights, generation samples, or comparable cross-run historical-best claim.

## Status, lessons and next experiment
- Result: **engineering safety candidate passed offline CI; Draft PR #70 remains unmerged; model promotion rejected**.
- Lesson: a remote terminal failure must not authorize another GPU run automatically. Explicit reviewed retry and normal same-data retrain are different approvals. A test-fixture newline error must be fixed and revalidated rather than presented as a passed test.
- Next controlled experiment: no-GPU status-matrix simulation of `COMPLETE`, `RUNNING`, `FAILED`, unknown and unauthorized remote responses, including ordinary push/schedule versus manual dispatch, to verify zero unauthorized pushes. Only after this and remote quota/rollback checks should PR merge and a new GPU training experiment be considered.
- The historical `DataCollatorForLanguageModeling` NameError is absent from current main; `response_only_collator` is retained and passed to Trainer. Do not reintroduce an unnecessary change.
- Do not commit secrets, tokens, private data, or modify security protections.
