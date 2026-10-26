# GPT-2 hourly audit — 2026-10-26 18:00 Asia/Shanghai

## Run and artifact evidence
- Daily [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137): completed/success at 2026-10-26 05:39 UTC; actual status `SKIPPED_NO_CHANGES`, `kaggle_kernel_submitted=false`, no current GPU updates or new evaluation. Main report: `reports/2026-10-26/run-40275426137`.
- New PR static CI [40304784787](https://github.com/mjw3177109/damoxingtest/actions/runs/40304784787): completed/success; job 121511102849, **236/236 unit tests PASS**, Ruff F821 PASS, response-only collator and -100 masking PASS. No CI Artifact.
- Latest Daily Artifact `12629319793` (5,186 bytes, not expired); source GPU Artifact `12487687305` (3,191,647 bytes, not expired). Artifact metadata checked, ZIP not re-downloaded this hour.
- Kaggle kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: public page inaccessible; live status, version, quota and concurrent/manual jobs **not independently verified**.

## Confirmed issue and bounded correction
- Hypothesis: Run-12 CPU temperature probe could load a changed `adapter_config.json` while only verifying `adapter_model.safetensors` SHA-256, making comparisons non-reproducible even with identical weight bytes.
- Root cause confirmed in PR code: `verify_adapter` previously only checked config-file existence; it did not parse or validate configuration.
- Minimal patch in `tools/run12_temperature_pair_cpu.py` (commit `171382fbb59839ee901ebdc08afddea9f861a6aa`): reject malformed config and mismatches against the recorded Run-12 recipe (base model, causal-LM task, LoRA r=8, alpha=16, dropout=0.05, fan-in/out, target modules c_attn/c_proj). Existing weight SHA-256 check retained.
- Tests updated in `tests/test_run12_temperature_pair_cpu.py` (commit `81b7eddf92a377e7a162732868e9c0471fca97a2`): three new negative cases for malformed config, mismatched recipe and mismatched target modules. CI **236/236 PASS** versus previous 233/233.
- **Limit**: actual archived Run-12 adapter config was not re-opened this hour; the strict check must be validated against the archived config before attempting real CPU inference. No new model inference performed; Transformers/PEFT and pinned base-model weights are unavailable in the current isolated environment. This patch is evidence integrity, not a quality improvement.

## Historical model evidence (not this hour)
- Source [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784): Tesla T4 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.2464554599, Val Loss 3.1472766399, PPL 23.2725985343; same-run base Val Loss 3.3892908096 (7.141% lower). Data: 85 training and 24 fixed holdout; train SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; holdout SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; base revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Current Daily `metrics.json` says `train_steps=0`, `train_loss=null`, `gpu_name=null`; all evaluation values reused. Current `samples.json`: 10 historical 64-character punctuation-only outputs (9 periods, 1 question marks), meaningful 0/10; no new generation.
- Main latest run directory verified to contain `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json`. Quality gate: `automated_precheck_passed=false`, `human_review_status=pending`, `promotion_approved=false`.
- Previous Run 8 uses a different validation dataset: no defensible cross-run historical-best improvement claim.

## Decision and next steps
- No GPU training, Kaggle submission, model promotion, merge, or security bypass. PR #70 remains Draft; preserve previous best/approved model.
- `DataCollatorForLanguageModeling` NameError no longer present; `response_only_collator` remains connected to Trainer and -100 masking is tested; do not repeat the historical fix.
- Next: independently verify archived adapter configuration and CPU dependencies, then execute the paired temperature 0.8 vs 0.7 inference on fixed prompts. Compare punctuation-only, EOS, repetition, and independently reviewed direct-answer rates; do not promote on heuristic improvements alone.
- Experience: weight-file integrity alone does not pin an adapter's effective behavior; configuration provenance is part of reproducible inference. CI passing does not imply Kaggle or model-quality success. No tokens, secrets or private prompt content written.
