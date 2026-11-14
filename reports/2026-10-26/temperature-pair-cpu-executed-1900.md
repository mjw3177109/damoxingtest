# GPT-2 hourly audit — 2026-10-26 19:00 Asia/Shanghai

## Decision
**Actual CPU inference completed; no new GPU training and no model promotion.** This hour's paired temperature experiment produced **no improvement** in the measured aggregate diagnostics. No further temperature tweak or GPU retry is justified from these data alone.

## Current workflow evidence
- New read-only CPU workflow: [Run 40311930881](https://github.com/mjw3177109/damoxingtest/actions/runs/40311930881), **completed/success**; job 121534971567. Workflow added on PR #70 branch in commit `3120a17e7022efda3a130b613ace89b762e4a317`. This is a CPU inference workflow, not Kaggle or GPU training.
- Static preflight: [Run 40311930678](https://github.com/mjw3177109/damoxingtest/actions/runs/40311930678), **completed/success**, 236 offline unit tests passing in the CPU job; no static CI Artifact.
- CPU workflow step evidence: exact rejected Run-12 Adapter download succeeded; pinned CPU dependencies installed; 236 tests passed; 20 paired generations executed; provenance/no-promotion checks passed; privacy-filtered Artifact uploaded.
- CPU Artifact: `12644064905`, `run12-temperature-pair-40311930881` (1,586 ZIP bytes, not expired at inspection), containing `temperature_pair.json`. The JSON was **actually downloaded and parsed**; SHA-256 `17e19b5428f80772254646492e49cf5a48f4c9dc632ec036ea50ba0eb683961f`.
- Latest Daily: [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137), completed/success **but actual `SKIPPED_NO_CHANGES`**, `kaggle_kernel_submitted=false`. Main report: `reports/2026-10-26/run-40275426137`.
- Latest Daily Artifact `12629319793` exists; historic GPU Artifact `12487687305` exists. No new GPU/model Artifact.
- Kaggle kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: live state, active version, quota, and manual/concurrent jobs not independently verifiable. **No Kaggle submission was made this hour.**

## Controlled CPU experiment: temperature 0.8 vs 0.7
Hypothesis: lowering sampling temperature from historical `0.8` to `0.7` may reduce punctuation-only generations. Single variable: temperature; fixed `top_p=0.9`, `no_repeat_ngram_size=3`, `repetition_penalty=1.12`, `max_new_tokens=64`, prompt SHA pairs, and per-prompt seed `42+index`.

- Source rejected training Run: [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784).
- Adapter weights SHA-256: `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`; adapter configuration verified against pinned Run-12 LoRA settings.
- Base model: `uer/gpt2-chinese-cluecorpussmall`, revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Fixed holdout SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; 10 matched prompts, 20 CPU generations total.
- Temperature **0.8**: punctuation-only **1/10**, inferred EOS **6/10**, maximum identical-character run **3**, mean generated tokens **38.7**.
- Temperature **0.7**: punctuation-only **1/10**, inferred EOS **6/10**, maximum identical-character run **3**, mean generated tokens **38.7**.
- Paired diagnostic difference: **0** on all four aggregate measures. Individual outputs and stop lengths differ, so this is *not* evidence that both decoding settings produce identical text.
- Direct-answer rate **not evaluated** (both arms `direct_answer_count=null`); raw model outputs intentionally absent from Artifact. Human semantic/safety review still required.
- `promotion_approved=false`; no improvement, no model upgrade, no GPU training.

## Historical training evidence (not new this hour)
- [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784): NVIDIA Tesla T4, 14.56 GiB, 3 epochs, **33 optimizer steps**, Train Loss **3.2464554599**, Val Loss **3.1472766399**, PPL **23.2725985343**, baseline Val Loss **3.3892908096**, same-run relative loss reduction **7.141%**; 85 train/24 validation records.
- Historical fixed samples: **10/10 punctuation-only**, including `................................................................`; meaningful responses **0/10**. No new training samples or new training metrics. The CPU temperature probe is a *separate inference test* and cannot overwrite the archived training samples.
- Latest Daily `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, and `quality_gate.json` all verified in main. Daily `train_steps=0`, `train_loss=null`, `gpu_name=null`, `automated_precheck_passed=false`, `promotion_approved=false`.
- Run 8 vs Run 12 use different validation sets: **no valid cross-run best-model ranking**. Preserve the prior approved model; do not label this as self-upgrade.

## Root cause, validation and next bounded step
- Confirmed blocker addressed this hour: the temperature experiment had no real inference execution, only a validated tool. Added a **read-only, least-privilege, same-repository PR #70-gated** CPU Actions workflow. It downloads a hash-pinned rejected adapter and emits only filtered numeric evidence; no Kaggle credentials, no secrets, no training, no promotion.
- Existing historical `DataCollatorForLanguageModeling` NameError is absent in current PR code; `response_only_collator` remains wired to Trainer. Do not repeat this fix.
- Measured temperature change did **not** improve the registered diagnostics. Do not repeat temperature-only experiments or spend GPU on this hypothesis.
- Next: investigate high historical training gradient norms and training/inference prompt-tokenization parity using **offline/CPU-only** evidence and explicit negative tests; evaluate semantic direct-answer quality separately under privacy controls. Only consider a new GPU run after actual Kaggle state/quota/concurrency and quality-gate checks are verifiable.
- No tokens, private data, or raw prompt/output text committed.
