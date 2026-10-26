# GPT-2 T4 hourly audit — 2026-10-26 16:00 Asia/Shanghai

## Scope and verified execution state
- Inspected GitHub Actions REST run list, Daily job steps/log, latest main report directory and files, PR #70, and Actions artifact metadata.
- Latest Daily [40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137): completed/success **but** `SKIPPED_NO_CHANGES`. `kaggle_kernel_submitted=false`; the Kaggle submission step was skipped. Latest main report: `reports/2026-10-26/run-40275426137`. This is not a new GPU run.
- Historical actual GPU source [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784): Tesla T4 14.56 GiB, 3 epochs, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; historical same-run baseline Val Loss 3.389291. Current Daily metrics: `train_steps=0`, `train_loss=null`, `gpu_name=null`. Do not claim cross-run best: Run 8 and Run 12 holdouts differ.
- Historical samples: 10/10 punctuation-only; meaningful responses 0/10. Current `quality_gate.json`: `automated_precheck_passed=false`, `human_review_status=pending`, `promotion_approved=false`. No new model output or quality improvement.
- Confirmed main files: `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json`, `status.txt`, `final_status.txt`. Latest Daily artifact ID `12629319793` (5,186 bytes, unexpired, report evidence only); historical GPU artifact ID `12487687305` (3,191,647 bytes, unexpired). No CI artifact or new model artifact.
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training` real-time state/version/quota **not independently verified**; public Kaggle page inaccessible. No new Kaggle submission, no GPU use in this audit.
- Historical `DataCollatorForLanguageModeling` NameError not present in current PR code; `response_only_collator` remains wired to Trainer. Do not repeat this fix.

## Controlled single-variable CPU experiment — implementation and tests
Hypothesis: changing only sampling temperature from historical 0.8 to 0.7 may change punctuation collapse on fixed Run 12 candidate. **This is a hypothesis, not a measured improvement.**

Added:
- `tools/run12_temperature_pair_cpu.py` (commit `08c8a305bb3171170e5757e5d9d8a4df64f91b87`)
- `tests/test_run12_temperature_pair_cpu.py` (commit `a29bf44619ec2bf3eb36e6e3b6a63988f3ae7649`)

The tool is read-only and explicitly CPU-only. It refuses to run without exact Run 12 Adapter SHA-256 `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c` and fixed holdout SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`. It pins base model `uer/gpt2-chinese-cluecorpussmall` revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`; fixed seeds 42+prompt index, 10 prompts, 64 tokens, top-p 0.9, no-repeat ngram 3, repetition penalty 1.12; only temperature differs (0.8 vs 0.7). Outputs numeric aggregates and prompt hashes, not raw prompts/output text or reversible generated token IDs. No automatic semantic-quality approval.

Local isolated 6/6 tests passed (with a local stand-in for existing diagnostic import); authoritative repository CI [40290029451](https://github.com/mjw3177109/damoxingtest/actions/runs/40290029451) at code SHA `a29bf44619ec2bf3eb36e6e3b6a63988f3ae7649` confirmed **230/230 tests PASS**, Ruff F821 PASS, response-only masking PASS. This CI runs offline tests only: **the actual model inference comparison was not executed**.

## Blockers, comparison, experience and next action
- Versus previous hour: tests 224 → 230; new CPU experiment runner and six negative/contract tests. GPU steps, Train/Val Loss, PPL, generation quality unchanged.
- Prior experimental baseline correction was important: historical temperature is 0.8, not 1.0. Run both arms with the same seed per prompt and preserve all other settings.
- Blockers: no authenticated Kaggle status/quota read; no available authorized workflow-dispatch action for an isolated CPU run; current local environment lacks verified Transformers/PEFT and base model cache. Do not invent inference results.
- Next: execute the read-only script in a controlled CPU environment with verified Adapter and holdout; compare punctuation-only count, EOS count and repeated-character lengths. Human review is required for direct-answer quality. Retain prior best version; do not start GPU Run 13 or promote based solely on punctuation changes.
- Protect users and humanity. Minimum privilege; no credentials, tokens, or personal information in commits/reports; no bypass of safeguards.
