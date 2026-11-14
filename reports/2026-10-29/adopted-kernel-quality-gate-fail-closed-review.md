# 2026-10-29 14:05 CST — Adopted Kernel quality-gate provenance audit

## Hypothesis and confirmed deterministic issue
Draft PR #72 already prevented an adopted existing Kaggle Kernel with unverified code/data provenance from being reported as fresh training success. However, the separate embedded Python quality gate in `.github/workflows/daily-gpt2-training.yml` read only the downloaded remote `training_status.json`, metrics, samples and adapter. If that remote output said `completed`, had positive validation-loss improvement, ten plausible answers and an adapter, the gate could set `automated_precheck_passed=true` even while this GitHub run's `status.txt` said `KAGGLE_EXISTING_KERNEL_REVIEW_REQUIRED`. This was an offline reproducible attribution defect, **not** evidence of a real Kaggle incident. Automatic promotion was already disabled and remains disabled.

## Minimal fix and regression
- Workflow commit `933767feea7886aa65ac6b73e8b5e8b38e7f2c3d`: read the current run's `status.txt` before evaluating the candidate. For `KAGGLE_EXISTING_KERNEL_REVIEW_REQUIRED`, append an explicit provenance rejection reason, mark `candidate_status=source_unverified`, and set `existing_kernel_provenance_unverified=true`. The automated gate cannot pass in that state, regardless of remote metrics or samples.
- Regression commit `180573b2d92e8f2ca46675284dd1d2ee9fcf455f`: execute the real embedded quality-gate Python offline with synthetic, otherwise-good metrics, ten meaningful samples and adapter. Test both remote `skipped_no_changes=false` and `true`. Both must fail closed; neither can promote.
- [Static Preflight Run 40827056518](https://github.com/mjw3177109/damoxingtest/actions/runs/40827056518), Job `123292395506`, SHA `180573b2d92e8f2ca46675284dd1d2ee9fcf455f`: **completed/success, 203/203 tests passed**. Python compile, Ruff F821 and response-only `-100` masking/Trainer wiring checks also passed.
- Previous workflow-only [Run 40827044400](https://github.com/mjw3177109/damoxingtest/actions/runs/40827044400): completed/success.

## Training provenance and controls
- Production `main` remained `361fa9ca36528eea70a7fea2d606c1bab50e24b8`. All changes are restricted to Draft PR #72; no merge or Kaggle submission.
- Latest production scheduled [Daily 40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324) is completed/success but `SKIPPED_NO_CHANGES`; no new training or evaluation. Its report is `reports/2026-10-27/run-40457573324`.
- Historical [GPU Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784): Tesla T4, 14.56 GiB, 3 epochs, 33 optimizer steps, Train Loss 3.2464554598837188, Val Loss 3.1472766399383545, PPL 23.272598534340947. Historical samples 0/10 meaningful; `promotion_approved=false`. These are not current-run metrics.
- Historical train data SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; validation SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; recipe SHA-256: `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Historical Kaggle canonical ID: `mjw3177109/damoxingtest-gpt-2-daily-training`. Live status, GPU quota and external concurrency remain **unverified**.
- As of the audit, the 2026-10-29 09:17 CST scheduled Daily had not appeared in GitHub's schedule run list; do not manually duplicate or declare the delayed run failed.

## Decision and next step
No model advancement. Keep PR #72 Draft until combined PR #72/#73 review, quota/concurrency confirmation, and protected deployment verification. Preserve the prior rollback version. Follow the next scheduled run, then perform a fixed-adapter, fixed-prompts CPU-only paired generation experiment when a safe execution path is available. Never treat a successful CI, a COMPLETE remote kernel, or a reused metric as model-quality proof.

## Reusable lesson
Provenance must gate **every** downstream quality claim, not only the final Markdown report. Synthetic, high-quality remote outputs are a useful adversarial regression fixture; unverified remote ownership must fail closed. No credentials, private data or model weights were committed.
