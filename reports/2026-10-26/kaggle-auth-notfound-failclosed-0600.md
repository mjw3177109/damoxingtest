# GPT-2 T4 | Kaggle authorization/not-found ambiguity regression | 2026-10-26 06:00 Asia/Shanghai

## Hypothesis, reproduction, and root cause
The PR #70 Daily workflow handled any nonzero `kaggle kernels status` output containing "not found" as an absent kernel, then attempted `kaggle kernels push`. A 403 authorization response can also say "Kernel not found" (e.g., private or inaccessible kernel). Treating it as a genuine 404 could submit a GPU job despite unverified access. This is a verified **code-path defect**, not evidence of an actual unauthorized Kaggle submission.

Added a no-network, no-GPU fake-CLI scenario returning exit code 1 and `403 Unauthorized: Kernel not found`. CI `40238538538` at test-only SHA `f9b970d12f3b9c95733a4ecf44e63f6a6780fa76` reproduced the defect: the mock incorrectly pushed and downloaded an output (`COMPLETE, True, True`) rather than blocking. 202 tests ran, 1 expected regression failure.

## Minimal fix and verification
- `.github/workflows/daily-gpt2-training.yml`: prioritize `401/403/unauthorized/forbidden/permission denied` error detection **before** the 404/not-found branch. Write `KAGGLE_STATUS_FAILED`, exit without pushing or downloading.
- `tests/test_kaggle_kernel_status_matrix.py`: new `unauthorized_missing` fixture and fail-closed regression.
- Candidate fix SHA: `7742dd397abb802c525230e2150ea54850be9d27`.
- GitHub Actions Static Preflight `40238551846` completed/success, Job `121305212969`: **202/202 tests passed**, including the new case; Ruff F821, Python compile, response-only collator and `-100` masking passed.
- Other status-matrix scenarios remain covered by existing tests. **No real Kaggle CLI call, Kernel submission, GPU training, or model evaluation** was performed for this patch.
- PR #70 remains Draft and unmerged. Main SHA at audit: `1237531d03cb3d43837e76da21d2a00b5d19cc24`.

## Historical training and provenance (not this hour's measurements)
- Latest Daily: Actions `40165941479` completed/success but `SKIPPED_NO_CHANGES`, `kaggle_kernel_submitted=false`; historical metrics/samples copied from `reports/2026-10-23/run-39921870784`.
- Latest real GPU evidence: Actions `39921870784`, Tesla T4 **14.56 GiB**, 3 epochs, **33** train steps, Train Loss **3.246455**, Val Loss **3.147277**, PPL **23.272599**. Model `uer/gpt2-chinese-cluecorpussmall`, LR `0.0002`, LoRA rank `8`, seed `42`, max length `256`.
- Training-data SHA256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; eval-data SHA256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; model revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Latest historical sample contains `................................................................`; meaningful responses **0/10**, human review pending, `promotion_approved=false`. Run 8 and Run 12 used different holdouts, so no cross-run best-model claim.
- Daily Artifact `12588187512` and historical GPU Artifact `12487687305` exist and are not expired. This CI created no model Artifact.
- Main latest date folder: `reports/2026-10-25`; PR branch date folder: `reports/2026-10-26`.
- Real-time Kaggle Kernel ID/status, manually initiated runs and GPU quota **not independently verified**.

## Decision and next steps
- **No new training results; no model promotion.** Keep PR #70 Draft and preserve rollback candidate; do not trigger Run 13.
- Lesson: remote "not found" text alone is not sufficient proof of nonexistence when the same error reports authorization failure. Fail closed before any GPU submission.
- Next: verify authenticated canonical Kernel ID/status and quota, confirm remote provenance and independent holdout/rollback, then review merge safety. A new GPU experiment requires a single measurable hypothesis and human-reviewed promotion evidence.
- The old `DataCollatorForLanguageModeling` NameError is absent on main, and `response_only_collator` remains wired to Trainer; do not repeat that fix.
- Protect users and humanity. Do not commit credentials, personal data, or bypass security checks.
