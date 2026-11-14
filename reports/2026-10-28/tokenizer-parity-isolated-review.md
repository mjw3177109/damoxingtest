# Run 12 inference-tokenizer parity: isolated review candidate (2026-10-28 CST)

## Scope and hypothesis

- Base `main` commit: `f46a904632afbc63ce8053a2a953e0400e3f16b0`.
- Historical GPU evidence: Actions Run `39921870784` (2026-10-23 UTC); **not a new training run**.
- Latest skipped Daily evidence: Run `40457573324` (2026-10-27 UTC), `SKIPPED_NO_CHANGES`.
- Data: training SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; validation SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Hypothesis: generation-time `tokenizer(prompt, return_tensors="pt")` did not explicitly match the training-time `add_special_tokens=False` contract. Aligning the call removes a possible train/inference tokenization discrepancy. It does **not** establish that this discrepancy caused the punctuation-only outputs.
- Historical observation: ten Run 12 samples were punctuation-only; the latest reused quality gate reported 0/10 meaningful samples and `promotion_approved=false`.

## Minimal change

- Change one generation-time tokenizer call in `scripts/train_gpt2_lora.py` to explicitly use `add_special_tokens=False`.
- Add offline AST regression tests for training-prefix, training-answer and generation prompt parity, plus the existing response-only collator contract.
- No training configuration, model weights, decoding settings, secrets, safety gate, or automatic promotion logic is intentionally changed.
- The wider PR #70 already contains the same one-line adjustment among many unrelated changes; this branch isolates it for independent review.

## Validation and safety gate

- Offline static/unit test evidence: [CI Run 40565933566](https://github.com/mjw3177109/damoxingtest/actions/runs/40565933566), Job `122407050436`, commit `08d39a1878c486f8a6f63ac1ec2ddf961fd5281c`: **completed/success**, Python compile PASS, 179/179 tests PASS, Ruff F821 PASS, response-only/-100 masking checks PASS. This is static validation only, not CPU inference or GPU training.
- New GPU training / Kaggle submission: **none**.
- New Train Loss, Val Loss, PPL, effective steps, or generated samples: **none**.
- Model promotion: **not approved**.
- **Merge hazard:** `training_recipe_hash()` hashes the entire `scripts/train_gpt2_lora.py` file. Merging even this inference-only line can invalidate the historical reuse key; the Daily workflow also triggers on `scripts/**` pushes to `main`. Therefore this PR must remain **Draft and unmerged** until the pre-submit reuse/remote-Kernel concurrency and quota behavior is independently verified and an explicit no-unnecessary-GPU path is established. Never force a training run to validate this patch.

## Next controlled steps

1. Inspect the new PR's actual CI logs; require Python compile, offline tests and existing static preflight to pass.
2. Independently verify the full recipe hash/reuse behavior and Kaggle remote state before any merge.
3. Only after safety review, use the fixed historical Run 12 adapter and ten fixed prompts for a CPU-only paired inference comparison; preserve raw prompts/outputs privately and publish only privacy-safe aggregates.
4. Compare meaningful answer rate, punctuation-only rate, EOS/short-answer rate and reference overlap. Keep `promotion_approved=false` without human-reviewed semantic evidence.
5. Preserve the previous approved model and avoid redundant GPU runs.

This report is an experiment hypothesis and change log, **not evidence of a model improvement**.

## 2026-10-28 04:03 CST follow-up: independent pre-submit safety audit

- Read the current `main` workflow `.github/workflows/daily-gpt2-training.yml` and `tools/pre_submit_reuse_guard.py` using the GitHub authorized connector. The workflow runs on `main` changes under `scripts/**`, invokes the reuse guard before Kaggle, and preserves the canonical kernel concurrency group. The PR #72 branch is not merged.
- Read `scripts/train_gpt2_lora.py` on `main`: `training_recipe_hash()` includes the complete bytes of `scripts/train_gpt2_lora.py`, the Kaggle notebook and requirements file; `find_reusable_run()` requires an exact recipe hash plus matching training/evaluation data SHA-256. This means the one-line generation-tokenizer change changes the hash input even though it does not alter the training objective. The existing historical reuse match is not guaranteed after merge. **Do not merge or launch GPU as a test of this hypothesis.**
- The workflow's canonical remote-kernel status check avoids duplicate submission for a recognized RUNNING/QUEUED/PENDING state, but for recognized COMPLETE/FAILED it permits a new push if reuse misses. That remote-state check is **not** a verified Kaggle quota check. The public Kaggle notebook could not be independently accessed; actual remaining quota and external concurrency remain unknown.
- Re-read Daily [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324): `training.log` says `PRE_SUBMIT_SKIPPED_NO_CHANGES`; `training_status.json` says `kaggle_kernel_submitted=false`; `metrics.json` says `train_steps=0` and `train_loss=null`. The 10 samples and Val Loss/PPL are historical evidence reused from GPU Run [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), not fresh measurements. `quality_gate.json` still says 0/10 meaningful samples and `promotion_approved=false`.
- Artifact API verification: Daily artifact `12713006845` (report archive, 5,182 bytes), historical GPU artifact `12487687305`, CPU EOS audit artifact `12696138797` all exist and were not expired at this check. PR #72 static CI has no training artifact, as expected.
- This follow-up is an audit-only document update on the Draft PR branch. No code behavior, training, model weights, credentials, quota settings, workflow security checks or promotion gates were changed. It is **not** evidence of model improvement.

### Next safe action

Keep PR #72 Draft. Design and separately test a fail-closed, no-unnecessary-GPU pre-submit path for inference-only changes, without allowing changes to the training recipe or data to be silently reused. Only then perform paired CPU inference on the fixed Run 12 adapter and ten fixed prompts, review semantic/safety quality, and consider a new training run after actual Kaggle quota/concurrency verification.


## 2026-10-28 05:06 CST: exact-snapshot no-GPU pre-submit hold (Draft only)

### Hypothesis and bounded implementation

- Risk: the generation-only tokenizer change modifies the full-script recipe SHA and could turn a scheduled/push Daily run into a redundant Kaggle submission even though training data and training objective are unchanged.
- New `tools/inference_only_submission_hold.py` compares **exact Git blob IDs** for the isolated training script, Kaggle notebook and Kaggle requirements, and SHA-256 for both train/evaluation datasets. Only the audited PR #72 snapshot matches. This is a one-time, explicit hold, **not** a general-purpose relaxation of recipe validation.
- `tools/pre_submit_reuse_guard.py` now emits `hold=true` and `BLOCKED_INFERENCE_ONLY_CHANGE` for that exact snapshot, writes a blocked `training_status.json` and a truthful `training.log`, and does **not** generate metrics, samples, or a Kaggle submission.
- Four Kaggle workflow steps (CLI install, kernel preparation, metadata validation, launch/monitor/download) now require `hold != true`. Existing concurrency, credential checks, training-recipe/data checks, promotion gate and approved adapter remain unchanged. A changed training script, notebook, requirements, or either dataset does **not** match the one-time hold and continues through the existing guarded path.
- The current guard is intentionally conservative and snapshot-specific. Do not treat it as proof that all future changes are safe or that Kaggle quota/concurrency has been independently verified.

### Commits and actual verification

- Implementation commits: `9d9438f49cf918f290db40b70b70476d52fa4295`, `819b5ff0c8b5b991700c61ec8fe3505ee6a8db4a`, `447c03b210caae38674a0e2dcfba038cad0d8753`, `0789af2f03aeb87c3ef413930c24ee260521de50`, `e6f0a525ed633bb1cdedd2962bc3acd68a094ec6`, `619ef467713b09fbd4d711545902591bb45a6e8b`.
- Local isolated test (5 cases): Python compile and unittest PASS. No GPU or network required.
- [GitHub Actions Static Preflight Run 40583847468](https://github.com/mjw3177109/damoxingtest/actions/runs/40583847468), Job `122470007648`, code SHA `619ef467713b09fbd4d711545902591bb45a6e8b`: **completed/success; 187/187 unit tests PASS, Python compile PASS, Ruff F821 PASS, response-only/-100 masking checks PASS**.
- Integration tests assert that the exact repository snapshot triggers `hold=true`, `reuse=false`, `kaggle_kernel_submitted=false`, and no new `metrics.json` or `samples.json`; they also check all four Kaggle steps are guarded and concurrency settings remain intact.
- These are offline tests and static workflow checks. **No production Daily execution of the new hold has occurred**; keep PR #72 Draft until an independent review of workflow and fail-closed behavior.

### Model evidence, comparison, decision

- Source GPU Run: `39921870784` (Tesla T4, 14.56 GiB, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599); historical values only.
- Latest Daily: `40457573324`, `SKIPPED_NO_CHANGES`, no new GPU or model samples. Historical generation quality 0/10 meaningful; `promotion_approved=false`.
- No new Kernel ID, model training, inference evaluation, quality improvement or promotion. Kaggle real-time status and remaining quota remain independently unverified. Historical Run 8 and Run 12 use different validation sets, so no cross-run best-model claim.
- Decision: **keep PR #72 Draft/unmerged**; preserve historical model and quality/safety gates. Before merging, review the one-time pinned hold and its operational impact, and test fixed-weight paired CPU inference separately. Only launch GPU when an actual training change is justified and Kaggle quota/concurrency can be checked.


## 2026-10-28 06:06 CST: truthful finalization of intentional GPU hold

- Independent code review identified a reporting gap: the exact-snapshot `BLOCKED_INFERENCE_ONLY_CHANGE` path correctly prevents Kaggle submission, but `scripts/finalize_report.py` previously grouped this intentional hold with generic missing-metrics errors and advised troubleshooting credentials/GPU as though training had failed. This did not cause a GPU submission; it caused inaccurate follow-up guidance.
- Minimal report-only fix commit `ca889aca8dc569fd36b78692cdd221e1444814f1`: explicitly report that no Kaggle kernel was submitted, no GPU training/evaluation occurred, and absent `metrics.json`/`samples.json` is expected for this hold. Next steps now specify independent guard review and fixed-weight CPU inference comparison. The final status remains `BLOCKED_INFERENCE_ONLY_CHANGE`, never `SUCCESS`; the existing workflow's fail-closed final-status condition is unchanged.
- Regression-test commit `7ccf9963a936efbe2cee5e383c8009e30dc2b98a`: new CPU-only `tests/test_inference_only_hold_finalization.py` constructs a synthetic blocked run and verifies truthful report, unchanged blocked final status, no fabricated metrics or samples, and no training-success claim.
- [Static Preflight Run 40592168433](https://github.com/mjw3177109/damoxingtest/actions/runs/40592168433), Job `122498907663`, code SHA `7ccf9963a936efbe2cee5e383c8009e30dc2b98a`: **completed/success, 188/188 unit tests PASS, Ruff F821 PASS**. The newly added blocked-finalization regression test passed. This CI is offline; it did not run Kaggle, inference, or training.
- At this check, the latest formal Daily is still `40457573324` (historical reuse, no new GPU), and latest actual GPU evidence remains Run `39921870784`. Main branch remains `f46a904632afbc63ce8053a2a953e0400e3f16b0`. Kaggle real-time Kernel status and remaining quota remain unverified. No new model quality result, no promotion.
- Decision: keep PR #72 **Draft and unmerged**. The intentional blocked state remains visibly non-successful at the workflow level; whether to classify it as an accepted operational skip requires separate review, not a silent relaxation of the failure gate. Preserve previous model, no duplicate GPU submission.


## 2026-10-28 16:03 CST: preserve deployed Daily schedule after PR #71

- **Observed integration risk:** main branch now uses `cron: "17 1 * * *"` after merged PR #71 (main commit `361fa9ca36528eea70a7fea2d606c1bab50e24b8`), but the still-Draft PR #72 workflow retained `cron: "0 1 * * *"`. Merging its workflow as-is could restore the old schedule. This is a verified branch-snapshot mismatch, not evidence of an actual regression on main.
- **Minimal correction:** workflow-only commit `79da350972e64f4ce1c7c36e0dbab2af945e0473` changes the PR #72 cron to 09:17 CST without modifying the canonical concurrency group, Kaggle submission steps, model code, data, or quality gate.
- **Regression guard:** test commit `41ce7c871191c01edd80351d210934d667e2ff4e` adds `DailyScheduleCompatibilityTests` to check the deployed cron, absence of old cron, canonical concurrency group, and `cancel-in-progress: false`.
- **Real CI evidence:** [Run 40654007981](https://github.com/mjw3177109/damoxingtest/actions/runs/40654007981) at `79da3509`: completed/success, 190/190 tests, Python compile and Ruff PASS. [Run 40654045140](https://github.com/mjw3177109/damoxingtest/actions/runs/40654045140) at `41ce7c87`, job `122700678443`: completed/success, **191/191 tests**, Ruff F821 PASS, response-only collator/-100 masking PASS. These are offline CI results, **not** production Daily, Kaggle or GPU training.
- **Training evidence unchanged:** latest scheduled Daily [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324) skipped before Kaggle submission; latest verified historical GPU [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Tesla T4 14.56 GiB, 33 steps, train loss 3.246455, val loss 3.147277, PPL 23.272599; ten historical generated samples remain punctuation-only (meaningful 0/10). No new Kernel ID, inference comparison, metrics, weights or model promotion.
- **Unresolved safety dependency:** PR #73 separately implements `KAGGLE_RETRY_REQUIRES_REVIEW` for failed remote kernels and is not merged; PR #72 still has the old terminal-failure retry branch. **Do not merge PR #72 or launch GPU** until both safeguards have been jointly reviewed, their merge order reconciled, and remote Kaggle status/quota independently checked. PR #72 remains Draft; no change to main.
- **Lesson:** a branch's own green CI is insufficient after main changes the same workflow. Recheck main-vs-PR configuration, add a targeted regression test, preserve failure-closed GPU gates, and distinguish verified engineering corrections from unverified model improvements.
