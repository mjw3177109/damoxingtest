# 2026-10-28｜Kaggle terminal-state retry guard (Draft PR #73)

## Hypothesis and observed root cause

The Daily workflow on main (`f46a904632afbc63ce8053a2a953e0400e3f16b0`) contained a terminal-state branch that set `NEED_PUSH=true` for a canonical Kaggle kernel reporting ERROR/FAILED/CANCELLED. A subsequent scheduled run with a recipe mismatch could therefore push another GPU job after a known terminal failure without root-cause review. This is a **verified code-path risk**, not evidence that any specific quota was consumed.

## Bounded fix

- Branch: `fix/gpt2-terminal-kernel-retry-review-20261028`
- Code commit: `13ad848565a16c0e9b1bade4bbbb37025b29e9f7`
- Regression-test commit: `eda6a9860683cb6afdbfed6fa6203c2f6a64af37`
- For a recognized existing terminal failure, set `KAGGLE_RETRY_REQUIRES_REVIEW` and exit before `kaggle kernels push`.
- Preserve existing first-run, COMPLETE, active-kernel monitoring, concurrency and promotion behavior. Do not disable safety controls.
- Added offline tests for terminal-state refusal and truthful non-success report finalization.
- [Static Preflight Run 40606805945](https://github.com/mjw3177109/damoxingtest/actions/runs/40606805945), Job `122548220031`, code SHA `eda6a9860683cb6afdbfed6fa6203c2f6a64af37`: **completed/success, 178/178 offline unit tests PASS (including both new retry-guard tests), Python compile PASS, Ruff F821 PASS**. No Kaggle submission or GPU training occurred. This document-only update does not change tested code.

## Training/evaluation evidence

- Latest formal Daily: [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324), `SKIPPED_NO_CHANGES`, no Kaggle submission, zero new steps.
- Historical GPU source: [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Tesla T4 14.56 GiB, 33 steps, train loss 3.246455, val loss 3.147277, PPL 23.272599. These are **not** new measurements.
- Historical samples: 0/10 meaningful, repeated punctuation. No new inference experiment, Kernel ID, model weights, or model promotion.
- Kaggle live status, quota, and external concurrency: not independently verified; public Kernel page inaccessible.
- Train/eval data SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c` / `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; unchanged.
- No secrets, credentials, private data, or checkpoint artifacts changed.

## Decision and next steps

Keep PR #73 Draft pending CI and independent review. Do not merge or launch GPU. On a real terminal failure, inspect Kaggle and Actions logs, identify root cause, verify a minimal fix and available quota/concurrency, then authorize a controlled retry using a separately reviewed mechanism. This PR prevents an automatic retry; it does **not** implement an authorization interface.

Model promotion remains rejected. Historical Run 8 and Run 12 use different holdout datasets, so no cross-run best-model claim is supported.

## 09:07 CST — Executable fake-CLI regression and lessons learned

- Hypothesis: a source-text assertion alone cannot prove that the actual shell step refuses a GPU push for each terminal Kaggle status.
- Added `tests/test_kaggle_terminal_retry_execution.py` to extract the launch step and execute it with a local fake `kaggle` command, with no credentials, network, model weights, or GPU. Cases: `KernelWorkerStatus.ERROR`, `Status: FAILED`, `KernelWorkerStatus.CANCELLED`, and `Status: CANCELLED`. The test checks `KAGGLE_RETRY_REQUIRES_REVIEW` and that no `kernels push` marker or push log exists.
- First attempt `525e82f44ab99fd403a3ab24542537fcc972939c`, [CI 40612994569](https://github.com/mjw3177109/damoxingtest/actions/runs/40612994569): **failed**, because the fake CLI checked argv[1] for `status` instead of the actual `kaggle kernels status` argument sequence. This was a **test-harness error**, not evidence of a production GPU retry. The failed test produced `KAGGLE_STATUS_FAILED`, still without a push.
- Minimal test-only correction `039c5d52dbc0820d1bae2bbefebaf1cab99daf84`: match both `kernels` and `status` / `push`. [CI 40613056770](https://github.com/mjw3177109/damoxingtest/actions/runs/40613056770), Job `122568995137`: **completed/success, 179/179 PASS**, Python compile and Ruff F821 PASS. This verifies the four terminal paths in an offline shell simulation, not a real Kaggle Kernel state.
- Comparison: prior tested PR #73 code SHA `c2227ceaa1120fd1e66270e41bd8a16b93889594`, [CI 40606892529](https://github.com/mjw3177109/damoxingtest/actions/runs/40606892529), 178/178 PASS. New coverage adds one executable regression; no training code, datasets, weights, secrets, GPU submissions, model samples, or quality gate were changed.
- Historical GPU reference remains Run `39921870784` (Tesla T4 14.56 GiB; 33 steps; train loss 3.246455, val loss 3.147277, PPL 23.272599). No new measurements, Kernel ID, or model promotion. Historical Run 8 versus Run 12 remains non-comparable because validation sets differ.
- Decision: **keep PR #73 Draft**, preserve rollback and fail-closed behavior. Next, independently review workflow integration and real remote status/quota before any authorized GPU retry. Never treat an offline simulated pass as a production Kaggle validation.

## 13:04 CST — Complete terminal-status spelling matrix

- Scope: test-only change to `tests/test_kaggle_terminal_retry_execution.py`; no production workflow, model, data, secrets, training configuration, or GPU behavior changed.
- Hypothesis: the existing executable fake-CLI test covered four of the six spellings accepted by the workflow regex, leaving `Status: ERROR` and `KernelWorkerStatus.FAILED` unexercised.
- Commit: `da83c0e8f3048073f5843f118cba2a24d8446c37`. Added the two missing spellings, so the offline shell test now exercises ERROR, FAILED, CANCELLED in both `KernelWorkerStatus.X` and `Status: X` formats; each must emit `KAGGLE_RETRY_REQUIRES_REVIEW` without `kaggle kernels push`.
- Real GitHub [Static Preflight Run 40635840553](https://github.com/mjw3177109/damoxingtest/actions/runs/40635840553), Job `122642485793`: completed/success, **179/179 tests PASS**, Python compile PASS, Ruff F821 PASS, response-only collator and -100 masking PASS. This verifies offline behavior only, not a live Kaggle Kernel or quota.
- Latest formal Daily remains [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324) (SKIPPED_NO_CHANGES, no Kaggle submission); no 2026-10-28 scheduled Daily run was visible in the 2026-10-28 13:04 CST API check. Historical five-run schedule delay averaged ~4h35m; this is an observation, not proof of a missed run.
- Historical GPU source remains Run `39921870784`: Tesla T4 14.56 GiB, 33 steps, train loss 3.246455, val loss 3.147277, PPL 23.272599; samples 0/10 meaningful, promotion rejected. No new model output, loss, or GPU work this hour.
- Limitation: GitHub CI does not establish live Kaggle state or remaining quota. PR #73 stays Draft, main and last rollback candidate unchanged. Next review: combined workflow behavior with PR #71 (cron) and PR #72 (inference-only GPU hold), and fixed-weight CPU inference quality comparison before any GPU submission.
- Lesson: a safety regex with multiple accepted formats needs a complete executable status matrix; test coverage is not equivalent to production deployment or model quality progress.
