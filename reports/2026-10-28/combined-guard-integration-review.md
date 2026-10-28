# 2026-10-28 16:58 CST — Combined Kaggle GPU safety guards (Draft PR #72)

## Confirmed integration risk and hypothesis

- Base `main`: `361fa9ca36528eea70a7fea2d606c1bab50e24b8`, Daily cron `17 1 * * *` (09:17 Asia/Shanghai).
- Prior PR #72 head: `2ca96c9ee74031dfb2f1a30e62c3178481ea820d`. Its exact-snapshot inference-only hold gated four Kaggle preparation/submission steps, but its terminal-failure branch still set `NEED_PUSH=true` for existing ERROR/FAILED/CANCELLED kernels.
- Draft PR #73 independently corrected the terminal-failure path. This review tests both protections together on PR #72, **without merging or starting Kaggle**.
- Hypothesis: terminal failure should require human review, while inference-only changes must still block all four Kaggle steps; scheduler, concurrency and model promotion protections must remain unchanged.

## Minimal branch-only change

- Workflow fix commit: `32861634604258a1a60e59ff1ae05ac20105bd59`. Replace only the terminal-failure retry branch with `KAGGLE_RETRY_REQUIRES_REVIEW` and immediate exit; no `kaggle kernels push` on that branch.
- Offline integration test commit: `acc71ef0972378967a0f04f7ed9d5fae37f5bf39`. Reuse PR #73's executable fake-CLI regression for all six accepted terminal-state spellings; additionally assert four `hold != 'true'` gates, canonical concurrency, `cancel-in-progress: false` and the deployed 09:17 cron.
- The exact-snapshot pin, training script, notebook, requirements, training/eval data, quality gate and credentials were not changed.
- Existing PR #73 remains Draft. This does not authorize either PR to merge automatically.

## Real CI and validation

- [Static Preflight Run 40660567642](https://github.com/mjw3177109/damoxingtest/actions/runs/40660567642), Job `122722269492`, head `acc71ef0972378967a0f04f7ed9d5fae37f5bf39`: **completed/success**.
- Raw job log: **193/193 unittest PASS**; six terminal-state shell simulations PASS; combined guard assertion PASS; Python compile PASS; Ruff F821 PASS; response-only collator and `-100` masking PASS.
- Previous PR #72 [Run 40654125040](https://github.com/mjw3177109/damoxingtest/actions/runs/40654125040): 191/191 PASS. The two extra tests are engineering coverage, not model improvement.
- No actual Kaggle status/remaining quota or cross-account concurrency verified. Public Kernel URL not accessible. No GPU allocation, new kernel push, model inference, or production Daily run was performed by this change.

## Historical training and quality baseline (NOT current-run results)

- Formal latest Daily [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324): `SKIPPED_NO_CHANGES`, historical metrics/samples reused; latest main report `reports/2026-10-27/run-40457573324`.
- Historical GPU [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784): Tesla T4, 14.56 GiB; 3 epochs, 33 effective steps, train loss 3.246455, val loss 3.147277, PPL 23.272599. Candidate outputs 0/10 meaningful, `promotion_approved=false`.
- Train SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`.
- Fixed eval SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- No comparable new metrics or generated samples. Run 8 vs Run 12 holdouts differ, so no historical-best improvement claim.

## Decision, rollback, next action and lesson

- **Keep PR #72 and #73 Draft**. Keep `main` and last rollback model unchanged. Do not spend GPU to test a merge.
- Next: independent diff/review of combined workflow and report-finalization status, live Kaggle quota/concurrency verification, then fixed-weight CPU-only generation comparison. Only validated quality improvement can justify promotion or a controlled GPU experiment.
- Lesson: individual PR CI success does not establish cross-PR compatibility; execute terminal-failure paths alongside exact-snapshot hold checks before merging.
- No secrets, tokens, personal data or model weights were committed.

## 2026-10-28 18:05 CST — Finalization safety regression

- **Hypothesis / gap:** PR #72's combined guard already had executable terminal-state CLI tests, but lacked a direct regression proving that `KAGGLE_RETRY_REQUIRES_REVIEW` finalizes as blocked, with no fabricated `metrics.json` or `samples.json`. The separate Draft PR #73 tested this; the combined candidate needs its own contract.
- **Minimal test-only commit:** `de20f6c4d48169f0e91f44aa0c2ecdd68b0af79e`; changed only `tests/test_kaggle_terminal_retry_execution.py`, adding a real offline `scripts/finalize_report.py` subprocess test. No production code, training data, model, credentials or Kaggle workflow execution changed.
- **Real CI evidence:** [Run 40669323946](https://github.com/mjw3177109/damoxingtest/actions/runs/40669323946), Job `122751796044`, `completed/success`; raw logs: **194/194 unittest PASS**, including `test_review_required_finalizes_as_blocked_without_fake_metrics`; Ruff F821 PASS; response-only collator and `-100` masking PASS.
- **Historical control only:** GPU Run `39921870784`, Tesla T4 14.56 GiB, 3 epochs / 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599. Training SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; evaluation SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`. No new GPU run, Kernel ID verification, inference samples, or model metrics this hour.
- **Comparison:** Prior combined CI Run `40660654854`: 193/193 PASS. Current Run `40669323946`: 194/194 PASS. This is one extra regression, **not** model improvement; historical Run 8 and Run 12 use non-comparable holdouts.
- **Promotion and rollback:** 0/10 meaningful historical generations; `promotion_approved=false`. Keep PR #72/#73 Draft, `main` unchanged, prior adapter rollback path intact. Kaggle live status, quota and remote concurrency remain unverified; no GPU launch authorized.
- **Lesson / next:** Verify both the execution path **and** report-finalization path for every blocked state. Next perform independent review of the combined workflow and obtain live Kaggle state before any controlled training; fixed-weight CPU-only generation comparison remains the first model-quality experiment.

## 2026-10-28 19:06 CST — Unknown status / authorization / rate-limit refusal

- **Hypothesis / safety gap:** the combined branch tests six terminal Kaggle states but lacks executable evidence that an unrecognized successful status response, a 403 authentication error, or a rate-limit error cannot reach `kaggle kernels push`. These are failure-mode tests, not claims that such failures happened in Kaggle.
- **Test-only commit:** `b96565dd8469a8ef00a131f4b378c8b7681e28a1`; add `test_unknown_or_unauthorized_status_cannot_push` in `tests/test_kaggle_terminal_retry_execution.py`. A fake Kaggle CLI supplies three response/exit-code cases; assert `KAGGLE_STATUS_FAILED`, no push marker and no push log.
- **Verified CI:** [Run 40677369252](https://github.com/mjw3177109/damoxingtest/actions/runs/40677369252), Job `122779100602`, `completed/success`, raw logs **195/195 unittest PASS**, Ruff F821 PASS, response-only collator and `-100` label masking PASS. Prior combined run `40669433407` passed 194/194. Extra coverage does not establish model quality improvement.
- **Current repository evidence:** `main` remains `361fa9ca36528eea70a7fea2d606c1bab50e24b8`; latest Daily `40457573324` remains `SKIPPED_NO_CHANGES`, with historical artifacts only. No 2026-10-28 Daily run appeared in the checked GitHub Actions list. Historical GPU Run `39921870784`: Tesla T4 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; historical valid generations 0/10, `promotion_approved=false`.
- **Limits / decision:** Kaggle live Kernel, GPU quota and remote concurrency are not independently verified; no GPU training, new samples, or new quality metrics. Keep PR #72/#73 Draft, preserve prior rollback adapter, do not merge or launch GPU from static CI evidence.
- **Lesson / next:** treat unknown API status, authorization errors and rate limiting as *fail closed*. Next independently inspect status classification and review integration before any production merge; fixed-weight CPU-only generation comparison remains the model-quality experiment. No credentials or personal data were recorded.

## 2026-10-28 20:00 CST — Existing active-kernel no-duplicate-push regression

- **Hypothesis / uncovered safety path:** Previous fake-CLI tests covered terminal failures, unknown status, authentication failure and rate limits, but did not execute the branch that discovers an already RUNNING, QUEUED or PENDING canonical Kaggle kernel. A new GitHub Run must monitor that remote job instead of submitting a duplicate GPU kernel.
- **Test-only change:** Commit `ac011cfcdc2619136d49cb141015a2304f576d14` adds `test_existing_active_kernel_is_monitored_without_duplicate_push` in `tests/test_kaggle_terminal_retry_execution.py`. A fake CLI reports three accepted active-state spellings and then COMPLETE; it supplies a dummy output file. Assertions require a COMPLETE status and downloaded mock output, with **no** `kaggle kernels push` marker or push log. No production workflow, training script, model weights, dataset, credentials or GPU jobs were changed.
- **CI evidence:** [Static Preflight Run 40684292602](https://github.com/mjw3177109/damoxingtest/actions/runs/40684292602), Job `122802597088`, head `ac011cfcdc2619136d49cb141015a2304f576d14`: raw job log showed **196 tests executed**, Ruff F821 PASS and response-only collator / `-100` masking PASS. Check the final workflow conclusion independently; job steps had completed successfully when logs were read.
- **Comparison:** Previous [Run 40677460401](https://github.com/mjw3177109/damoxingtest/actions/runs/40677460401) had 195/195 passing tests. The additional regression expands safety coverage only; **not** evidence of better model performance.
- **Historical training baseline (not a new run):** GPU [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Tesla T4 14.56 GiB, 3 epochs / 33 effective steps, train loss 3.246455, val loss 3.147277, PPL 23.272599; 0/10 meaningful samples, promotion denied. Train data SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; fixed eval SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- **Limitations and decision:** Latest formal Daily remains [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324), `SKIPPED_NO_CHANGES`. Live Kaggle status, remaining quota and cross-account concurrency were not independently verifiable. Keep PR #72/#73 Draft and previous rollback model unchanged. No GPU launch, new training or candidate promotion.
- **Lesson / next:** Verify the *active* remote-kernel path as well as failure paths before production merge; do not mistake a mocked COMPLETE response for real training success. Continue independent workflow review and fixed-weight CPU-only quality comparison.

## 2026-10-28 21:02 CST — Mixed Kaggle status errors fail closed

- **Deterministic root cause / hypothesis:** In the combined Draft PR #72, the nonzero-exit status classifier searched for `404|Not Found|not found` before checking authorization/rate-limit errors. A CLI response such as `403 Forbidden: user not found (404)` or `429 API rate limit exceeded: kernel not found` could therefore be misclassified as a missing kernel and reach `kaggle kernels push`. This was established from source control flow and local shell regex checks, **not** observed on the live Kaggle service.
- **Minimal production fix:** Commit `701baee673c6cb4da4111b17b8880116e65e909b` gives 401/403/429, Forbidden/Unauthorized/permission-denied and rate-limit indicators priority over kernel-absence handling, writes `KAGGLE_STATUS_FAILED`, and exits before push. Genuine explicit 404/kernel-absence responses retain the existing first-run path. No credentials, dataset, notebook, model weights, quality gate or schedule were changed.
- **Regression:** Commit `86f547c9f75d74356c2af82e2611309357e33b68` extends the existing executable fake-CLI test with two mixed-error outputs. Both must return `KAGGLE_STATUS_FAILED`, leave no push marker and create no push log. Local shell regex checks also distinguish mixed 403/429 from an ordinary 404; no Kaggle API was called.
- **Verified CI:** [Run 40692773217](https://github.com/mjw3177109/damoxingtest/actions/runs/40692773217), Job `122831566526`, head `86f547c9f75d74356c2af82e2611309357e33b68`: **completed/success**, raw job log **196/196 unittest PASS**, Ruff F821 PASS, response-only collator and `-100` masking PASS. [Prior Run 40684401617](https://github.com/mjw3177109/damoxingtest/actions/runs/40684401617) also passed 196/196; the test count is unchanged because two subcases were added to an existing test.
- **Historical control (not this hour):** Daily Run `40457573324` was `SKIPPED_NO_CHANGES`. GPU Run `39921870784`: Tesla T4 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599, 0/10 meaningful generations; `promotion_approved=false`. Train data SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`, eval SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`. No new GPU steps, inference samples or comparable model metrics; historical Run 8 and Run 12 use different holdouts.
- **Decision / rollback:** Keep PR #72/#73 Draft and `main` at `361fa9ca36528eea70a7fea2d606c1bab50e24b8`; preserve prior adapter. Remote Kaggle Kernel state, remaining GPU quota and concurrent jobs remain unverified. No training or promotion authorized. The branch fix is reversible by reverting these two commits.
- **Lesson / next:** Never infer absence of a remote resource from ambiguous error text; prioritize authentication and quota failures over a secondary 404 phrase. Before any production merge, independently review the first-run 404 path, verify live Kaggle state/quota, and run fixed-adapter CPU-only generation comparisons. No secrets or personal information recorded.
