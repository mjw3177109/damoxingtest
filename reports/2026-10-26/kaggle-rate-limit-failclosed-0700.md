# GPT-2 T4 | Kaggle transient-status fail-closed audit | 2026-10-26 07:00 Asia/Shanghai

## Hypothesis and risk
A failed `kaggle kernels status` request containing both a transient API error and the phrase "Kernel not found" could enter the existing 404/not-found branch and submit a GPU job. This is a **code-path risk**, not evidence that an actual Kaggle 429/503 response or duplicate submission occurred.

## Minimal change
- `.github/workflows/daily-gpt2-training.yml`: before interpreting a nonzero status as 404/not-found, reject rate limits (429, too many requests, rate-limit text) and 5xx/upstream service errors. Mark `KAGGLE_STATUS_FAILED`; do not push/download.
- `tests/test_kaggle_kernel_status_matrix.py`: add fake-CLI scenarios `429 Too Many Requests: Kernel not found` and `503 Service Unavailable: Kernel not found`, asserting no push and no download.
- Preserve previous 401/403 authentication protection, real 404 first-submission path, active-kernel protection, manual failed-kernel retry approval, and same-data retrain approval.
- Implementation SHA: `97a7ae4674e084453592b8f973aed2cdbbec2e7e`; regression-test SHA: `bf9771cbd4f588443bc595f8b0199d99787d9037`.
- GitHub Actions Static Preflight Run `40243121556`, Job `121318980118`: **completed/success, 203/203 tests**, including the new test; static checks passed. Run `40243110020` also completed/success for the preceding workflow-only commit.
- Tests execute the real extracted Bash workflow step with a fake Kaggle CLI, **without network or GPU**. Real Kaggle status/quota and end-to-end provenance are still unverified.

## Training provenance (historical, not this hour)
- Latest Daily Run `40165941479`: completed/success but `SKIPPED_NO_CHANGES`, `kaggle_kernel_submitted=false`, reused evidence from `reports/2026-10-23/run-39921870784`.
- Last verified real GPU training: Actions `39921870784`, Tesla T4 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; 85 training and 24 validation records. No new GPU training or model evaluation in this run.
- Train SHA256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; validation SHA256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Latest historical samples contain repeated punctuation (e.g. `................................................................`); meaningful outputs 0/10; `promotion_approved=false`.
- Artifacts verified via GitHub API: latest Daily `12588187512` and last real GPU `12487687305`, both unexpired. No new model artifact.
- Run 8 and Run 12 used different validation sets; **no defensible cross-run best-model improvement claim**.

## Decision and lessons
- Keep PR #70 **Draft**, no merge, no new GPU submission, no promotion. Main report directory remains `reports/2026-10-25`; this audit is on the PR branch under `reports/2026-10-26`.
- Lesson: an HTTP error body containing "not found" is insufficient to authorize resource creation when the request was rate-limited or failed upstream. Fail closed and wait for a verified status.
- Next: authenticated check of canonical Kernel ID, current remote version/status, quota and artifact provenance; validate rollback and independent holdout before any one-hypothesis GPU experiment. Do not automatically retry transient errors.
- Historical `DataCollatorForLanguageModeling` NameError is absent from main; `response_only_collator` remains wired into Trainer. No redundant fix.
- Protect users and humanity; never commit tokens, credentials, or personal data.
