# GPT-2 hourly audit — tokenizer prompt parity — 2026-10-26 21:36 Asia/Shanghai

## Decision
**Verified small code fix and offline tests; no GPU training or new model quality evidence. Promotion remains rejected.** The Run 12 candidate remains quarantined; PR #70 stays Draft. No Kaggle kernel was submitted.

## Verified source evidence
- Repo `mjw3177109/damoxingtest`, branch `fix/reuse-training-config-20261025-22`; fix commit `9920cf4f7e49eadd5a62d467da4b2e2e8c916a99`.
- Previous head `6667e2c0d15f614d9580842f22dc2777aa6aec98`.
- [Static CI 40332473695](https://github.com/mjw3177109/damoxingtest/actions/runs/40332473695) completed/success at fix commit; Job `121605180662` logs: **244/244 unittest PASS**, Ruff F821 PASS, response-only collator / `-100` mask wiring PASS, Python compilation PASS. These checks do not run the actual model.
- [Latest Daily 40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137) completed/success but **SKIPPED_NO_CHANGES**, `kaggle_kernel_submitted=false`. No new training or evaluation.
- Latest main report `reports/2026-10-26/run-40275426137/`: `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json` individually fetched and verified.
- Artifact metadata verified: Daily `12629319793` (exists, not expired), historical GPU `12487687305` (exists, not expired), prior CPU probe `12644064905` (exists, not expired). No new model Artifact. Latest static CI has no model artifact.
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: live status, current version and remaining quota **not independently verified**; direct public page inaccessible. Do not infer idle/ready.

## Root cause hypothesis and narrow fix
The training supervision path explicitly encoded both prompt prefix and response with `add_special_tokens=False`, but three generation entrypoints omitted the option and relied on the tokenizer's default. This is a **confirmed API-contract inconsistency**, not proof that the specific pinned tokenizer inserted extra tokens or caused punctuation collapse.

Changed only:
1. `scripts/train_gpt2_lora.py`: generation prompt now explicitly sets `add_special_tokens=False` to match the supervised training prefix.
2. `tools/generation_decode_probe.py`: same explicit setting for base-vs-candidate CPU diagnostics.
3. `tools/run12_temperature_pair_cpu.py`: same explicit setting for the paired CPU temperature diagnostic.
4. Added `tests/test_tokenizer_prompt_contract.py`: 3 offline tests for response-only tokenization, all generation callsites and identical Chinese chat prefixes.

No change to the response-only collator, label mask, training hyperparameters, data, safety gate, GPU submission or approved adapter. The historical Run 12 results are not reclassified. This code change alters the training recipe hash, so any eventual merge must be reviewed under the existing pre-submit safety gate; **do not auto-trigger retraining from this audit**.

## Training provenance and historical metrics (not measured this hour)
- Historical GPU: Tesla T4 **14.56 GiB**, 3 epochs, **33 optimizer steps**, 85 train / 24 fixed validation examples.
- Historical Run 12: Train Loss **3.246455**, Val Loss **3.147277**, PPL **23.272599**, same-run baseline Val Loss **3.389291**, improvement **7.141%**.
- Training data SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; fixed holdout SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; historical recipe SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Base model revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`; historical training-side exact Git SHA was not recorded and must not be invented.
- Latest Daily: `train_steps=0`, `train_loss=null`, `gpu_name=null`. All cited losses and PPL are reused historical values.
- Historical greedy generation: **0/10 meaningful**, 10/10 punctuation-only (representative 64 dots). No new generated samples this hour. Previous CPU 0.8-vs-0.7 probe had equal aggregate diagnostics; semantic direct-answer rate unassessed.
- `quality_gate.json`: `automated_precheck_passed=false`, `promotion_approved=false`, `human_review_status=pending`. Run 8 vs Run 12 fixed holdouts differ; no cross-run best claim.

## Known blockers, learned lesson, next bounded experiment
- The historical `DataCollatorForLanguageModeling` NameError is absent from current source; `response_only_collator` remains connected to Trainer. No duplicate patch.
- Lesson: training and inference must state the same tokenizer special-token policy explicitly; relying on defaults creates an avoidable reproducibility ambiguity. Static parity is **not** proof of semantic quality improvement.
- Next controlled step: with the pinned base tokenizer and archived Run 12 Adapter, compare token ID sequences from the former default encoding and explicit `add_special_tokens=False` for the 10 fixed prompts on CPU. Record how many prompts actually differ, EOS/PAD IDs, and token-length deltas, without exporting raw prompts or token IDs. If 0/10 differ, record this fix as preventive and do not claim it explains generation collapse. Then inspect EOS supervision/truncation and independent semantic quality.
- Before any GPU restart: independently verify Kaggle status, quota, concurrency, approved rollback adapter and the new recipe's end-to-end tests. Keep PR Draft until reviewed.
- No tokens, credentials, private content or personal data were written.
