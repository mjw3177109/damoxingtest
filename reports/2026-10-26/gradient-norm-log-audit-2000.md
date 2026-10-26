# GPT-2 hourly evidence audit — 2026-10-26 20:00 Asia/Shanghai

## Decision
A read-only gradient-norm log audit and its five regression tests were added. No new Kaggle/GPU training, no new model weights, no semantic quality improvement, and **no promotion**. Do not infer failed gradient clipping solely from the logged norms.

## Source evidence and provenance
- Source GPU training: [Actions Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), archived under `reports/2026-10-23/run-39921870784/` on main.
- Training log: `reports/2026-10-23/run-39921870784/training.log`; Git blob SHA `c562543cbe47b85cd9c534d7b7f70610d8812c12`.
- Historical data SHA-256: train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; validation `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; recipe `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Source base model `uer/gpt2-chinese-cluecorpussmall`, resolved revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`. Historical training-side exact Git commit was not recorded; do not invent it.
- Historical GPU: Tesla T4, 14.56 GiB, 85 train / 24 validation examples, 3 epochs, 33 optimizer steps, LR 0.0002, `max_grad_norm=1.0`, `fp16=True`.
- The latest Daily [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137) completed but was `SKIPPED_NO_CHANGES` with `kaggle_kernel_submitted=false`. The most recent Daily report directory on main is `reports/2026-10-26/run-40275426137`.
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: live status, current version and GPU quota were **not independently verified**. No submission attempted.

## Diagnostic hypothesis and real log observations
Hypothesis: unusually large logged gradient norms may help explain generation collapse. Read-only parsing of the historical real training log found seven numeric `grad_norm` entries:
- Step 1: 39550.09375
- Step 5: 41631.30078125
- Step 10: 61934.7109375
- Step 15: 67372.71875
- Step 20: 68622.515625
- Step 25: 70956.7890625
- Step 30: 72079.8203125

Observed min **39550.09375**, max **72079.8203125**; 7/7 logged values exceed the configured clipping threshold 1.0. Trainer gradient norms are generally logged **before** clipping, so these observations **do not demonstrate that clipping was skipped** and do not establish causality for punctuation-only generations. No NaN/Inf was observed in these seven logged values. This is an offline diagnostic, not a new model experiment.

## Minimal engineering work and validation
- Added `tools/gradient_norm_audit.py` at commit `91341fda2fd3b81bb7ff74a6e5b898dfddbbf42e`. It parses Trainer metric dictionaries safely with `ast.literal_eval`, validates finite nonnegative norms and monotonic steps, and emits numeric-only evidence with a log SHA-256. No raw log/prompt/output is included.
- Added `tests/test_gradient_norm_audit.py` at commit `7ce90f4e151756b1ccef0cb2aff652771ad42d4d`, five offline regression tests for normal logs, missing records, invalid norms, duplicate/out-of-order steps, invalid thresholds and no raw-text leakage.
- Local isolated checks: **5/5 PASS**, Python compilation PASS.
- [Static Preflight Run 40319116181](https://github.com/mjw3177109/damoxingtest/actions/runs/40319116181) completed/success at head `7ce90f4e151756b1ccef0cb2aff652771ad42d4d`, Job `121559207968`; actual CI log says **Ran 241 tests**, `OK`, `All checks passed!`. CI tests the diagnostic tool; it does **not** execute the tool against the historical log.
- No training code, Kaggle workflow, model weights, model promotion policy or security controls were modified.

## Historical metrics and quality gate (not new measurements)
- Train Loss **3.2464554599**, Val Loss **3.1472766399**, PPL **23.2725985343**; same-run baseline Val Loss **3.3892908096** (7.141% decrease). Run 8 and Run 12 use different holdouts; cross-run historical best remains not comparable.
- Latest Daily `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json` and `quality_gate.json` were read or their presence confirmed. Latest Daily `train_steps=0`, `train_loss=null`, `gpu_name=null`.
- Historical training greedy samples: **0/10 meaningful**, 10/10 punctuation-only (e.g. 64 dots). New CPU paired temperature probe [40311930881](https://github.com/mjw3177109/damoxingtest/actions/runs/40311930881) previously produced 20 diagnostic generations: temperature 0.8 and 0.7 both 1/10 punctuation-only, 6/10 inferred EOS, max identical run 3, mean 38.7 tokens; direct-answer quality not evaluated. This is **previous-hour evidence**, not a new result.
- Artifacts: latest Daily `12629319793` exists; historical GPU `12487687305` exists; previous CPU experiment `12644064905` exists; this static CI produced no Artifact. No new model Artifact.
- Quality gate `automated_precheck_passed=false`, `promotion_approved=false`, human review pending. Previous approved model preserved.

## Root cause, experience and next bounded step
- Confirmed historical `DataCollatorForLanguageModeling` NameError is absent from current training code; `response_only_collator` remains wired to Trainer. No duplicate repair or GPU retry.
- Lesson: do not equate a large **logged pre-clipping norm** with a failed clip operation. Confirm actual optimizer/unscale/clip ordering and the label-mask/tokenizer/prompt path before altering training precision or hyperparameters.
- Next: perform a controlled offline/CPU training-vs-inference tokenization parity audit, including EOS, PAD, response-only `-100` labels and prompt-prefix alignment. Do not run a new GPU experiment without verified Kaggle status, quota, concurrency guard and rollback path.
- All committed evidence is sanitized; no credentials, tokens or private data.
