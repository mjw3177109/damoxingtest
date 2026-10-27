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
