# GPT-2 hourly audit — 2026-10-26 17:00 Asia/Shanghai

## Verified run state
- GitHub Actions Daily [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137): completed/success, but actual `SKIPPED_NO_CHANGES`; `kaggle_kernel_submitted=false`; Kaggle launch/download steps skipped. Main report: `reports/2026-10-26/run-40275426137`.
- Latest verified static CI after patch: [40297369220](https://github.com/mjw3177109/damoxingtest/actions/runs/40297369220), completed/success, **233/233 tests passed**, including three new provenance regression tests. Ruff F821 and response-only collator checks passed.
- Latest Daily Artifact `12629319793` (5,186 bytes, unexpired), historical GPU Artifact `12487687305` (3,191,647 bytes, unexpired). No new model Artifact; static CI has no model Artifact.
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: live status, version and quota not independently accessible. Do not infer remote status from Actions success.

## Historical training and quality (not this hour)
- Source [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), NVIDIA Tesla T4, 14.56 GiB, 3 epochs, 33 effective steps; Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; same-run baseline Val Loss 3.389291 (7.141% reduction). Run 8 and Run 12 evaluation datasets differ, so no defensible cross-run best claim.
- Current Daily `metrics.json`: `train_steps=0`, `train_loss=null`, `gpu_name=null`. `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json` all present in main's latest report directory. `samples.json` reuses 10 historical outputs, all punctuation-only (0/10 meaningful); no new generation. `automated_precheck_passed=false`, `human_review_status=pending`, `promotion_approved=false`.
- Current PR source `scripts/train_gpt2_lora.py` does not reference `DataCollatorForLanguageModeling`; `response_only_collator` remains wired to Trainer. No duplicate fix.

## Root cause and minimum verified correction
- The newly added read-only CPU temperature comparison runner previously aggregated rows per temperature without requiring the **same prompt index and SHA-256 in each arm**. A missing, duplicated, or different prompt could produce misleading differences between temperature 0.8 and 0.7, even though the runner normally generates matched pairs.
- Modified only `tools/run12_temperature_pair_cpu.py` (commit `cacc26a383a882c3f5378d3e7861fa3943bd5b06`) and `tests/test_run12_temperature_pair_cpu.py` (commit `fcd234eb775b0ad30e73b24b6e9a37da706b8512`).
- Summary now fails closed for invalid prompt indices/digests, duplicate indices within an arm, and differing prompt sets/hashes across arms. Added three negative regression tests. CI [40297369220](https://github.com/mjw3177109/damoxingtest/actions/runs/40297369220) confirmed **233/233 PASS**.
- This is experiment-evidence integrity, not a model improvement. No CPU model inference, GPU training, Kaggle submission, architecture changes, or model promotion performed.

## Comparison, lessons and next action
- Previous hour: 230 tests; current: 233. Model weights, steps, Loss/PPL, generation quality and promotion state unchanged.
- Lesson: a single-variable experiment needs **paired provenance per prompt**, not just identical sampling settings and two nonempty groups.
- Next: in a verified CPU environment with Transformers/PEFT, pinned base model and SHA-verified Run 12 Adapter/holdout, execute the temperature 0.8 vs 0.7 comparison; inspect punctuation-only/EOS/repetition metrics and independently review semantic direct-answer quality. Current local environment lacks Transformers/PEFT and cannot access the remote base model, so inference is blocked. Kaggle quota/runtime cannot be verified, so do not start GPU Run 13.
- Preserve previous approved model and all safety checks. No credentials, tokens or private information recorded.
