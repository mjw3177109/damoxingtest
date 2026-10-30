# 2026-10-29 00:08 CST — Kaggle polling authentication/rate-limit precedence (Draft PR #72)

## Hypothesis and confirmed code risk

The `Launch, monitor, and download` shell step previously checked polling errors only when the Kaggle CLI exit code was nonzero. If a CLI wrapper returned exit code 0 while its text contained `429 Too Many Requests`, the workflow could continue polling for up to 210 minutes. A mixed `KernelWorkerStatus.COMPLETE` + `429` response could be interpreted as success. This is a **source-level control-flow risk**; no real Kaggle incident was observed.

## Minimal repair and validation

- Branch: `fix/gpt2-prompt-tokenizer-parity-20261028`; production `main` was not changed.
- Repair: classify `401/403/429`, unauthorized, forbidden, and rate-limit text **before** COMPLETE in the polling loop, independent of CLI exit code. Existing active-kernel reuse and one-time genuine 404 creation behavior remain covered by tests.
- Workflow fix commits: `2c1c108c6d1148a0b4ac2e3d813ac64d3f2daf15` and corrective `e391cf859098fd2e5712655feaa3a3391831237b`.
- Test commits: `7199abbc813e1a89c762389d9513e619126834f6` and `053a9a5b60af5abffec52adbb3579df9aee6082a`.
- **Failure and recovery:** Early static CI runs [40722793096](https://github.com/mjw3177109/damoxingtest/actions/runs/40722793096), [40722819726](https://github.com/mjw3177109/damoxingtest/actions/runs/40722819726) and [40722860999](https://github.com/mjw3177109/damoxingtest/actions/runs/40722860999) failed because the first workflow text edit accidentally truncated a quoted shell regex, yielding `unexpected EOF while looking for matching \`'\``. This was a deterministic editing error, **not** a Kaggle training failure. The full polling block was restored before acceptance.
- **Passing verification:** [Static Preflight Run 40722955641](https://github.com/mjw3177109/damoxingtest/actions/runs/40722955641), Job `122938489184`, head `e391cf859098fd2e5712655feaa3a3391831237b`, `completed/success`. Raw log: **198/198 unittest PASS**, including the extended fake-CLI polling test for exit 0 / 429 and mixed COMPLETE+429; Ruff passed; response-only collator and `-100` masking passed. This is offline validation only.
- Engineering lesson: edit shell blocks atomically and verify syntax before committing. Do not treat green CI or a simulated COMPLETE response as proof of real model training.

## Historical control — no new training

- Latest formal Daily: [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324), `SKIPPED_NO_CHANGES`, source `reports/2026-10-23/run-39921870784`.
- Last archived GPU training: [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Tesla T4 **14.56 GiB**, 3 epochs, 33 effective steps, Train Loss **3.246455**, Val Loss **3.147277**, PPL **23.272599**. Historical fixed-holdout baseline Val Loss **3.389291**.
- Training data SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; evaluation SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`. Model commit: `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Historical generation: 0/10 meaningful samples; punctuation repetition; `promotion_approved=false`. No new GPU, new Kernel, new metrics, or new samples in this repair.
- Kaggle Kernel ID: `mjw3177109/damoxingtest-gpt-2-daily-training`; live authenticated status, remaining quota, and cross-run concurrency **not independently verified**.
- Comparison with preceding PR #72 static CI: 198/198 remained 198/198. Additional test scenarios improve regression coverage, **not** model quality. Historical Run 8 and Run 12 evaluation sets differ; no cross-run best-model claim is justified.

## Decision and next action

Keep PR #72 and PR #73 Draft; do not merge or initiate GPU training until an independent production review, live Kaggle state/quota verification, and fixed-weight CPU generation comparison are complete. Keep the last rollback model and existing quality gate. Never log credentials, bypass safety protections, or promote an unreviewed adapter.
