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

- Offline static/unit test evidence: **pending GitHub CI** at time of authoring; do not infer success from source inspection.
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
