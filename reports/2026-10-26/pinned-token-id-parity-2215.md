# GPT-2 hourly evidence audit — real Run 12 prompt token-ID parity — 2026-10-26 22:15 Asia/Shanghai

## Decision
**Confirmed real training/inference token-ID mismatch in the historical default generation path; root cause of punctuation collapse remains unproven. No GPU training, model promotion, or merge.** PR #70 stays Draft.

## Newly executed work and provenance
- New read-only CPU audit tool: `tools/audit_prompt_token_id_parity.py`; tests: `tests/test_prompt_token_id_parity.py`; targeted push-only workflow: `.github/workflows/run12-prompt-token-id-parity-cpu.yml`.
- Commits: tool `62a66f9f2053bfba629627a2d6e9940d4bbe0d31`, five tests `3d8456557b68a34a7abccade667102636ba8480d`, workflow `e5c02341028ed845f160be8879f3d0e4816bab68`.
- [Real CPU tokenizer audit Run 40337794769](https://github.com/mjw3177109/damoxingtest/actions/runs/40337794769): **completed/success**, pinned `transformers==4.46.3`, no GPU or model inference, five targeted tests PASS. Artifact `12658350390` actually downloaded, inspected, and verified; archive `run12-prompt-token-id-parity-40337794769`, unexpired.
- Extracted `token_id_parity.json` SHA-256: `25494c987e566cc0b4b76b9f638dc9b17a62a9639f15c7c6908d094f92bf4e2c`.
- [Static CI Run 40337763810](https://github.com/mjw3177109/damoxingtest/actions/runs/40337763810): **completed/success**, 249/249 unit tests PASS, Ruff F821, response-only collator and -100 label mask checks PASS. Static CI has no model artifact.

## Real tokenizer experiment
- Base tokenizer: `uer/gpt2-chinese-cluecorpussmall` pinned revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`; actual class **BertTokenizerFast**.
- Fixed holdout: `data/safety_humanity_eval_v1.jsonl`, SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; first 10 fixed prompts.
- Historical inference behavior: `tokenizer(prompt)` (default special-token policy). Training prefix: `tokenizer(prefix, add_special_tokens=False)`. Corrected PR inference: explicit `add_special_tokens=False`.
- **10/10 prompts have different actual token-ID sequences** between historical default and corrected explicit-false encoding.
- **10/10 prompts differ in length by exactly +2 tokens under the historical default**; example: prompt 0 default 38 vs explicit-false 36. All 10 lengths were checked from the actual artifact.
- EOS token ID **102**, PAD token ID **0**, BOS token ID **null**. These are tokenizer metadata, not raw prompt/token-ID exports.
- This demonstrates a real input-format mismatch, not just a style-contract discrepancy. It is consistent with BertTokenizerFast's special-token wrapping; the audit did not directly classify the two added token IDs, so avoid claiming their identities were individually verified.
- **Causal boundary:** No corrected model forward/generation was performed. Do not claim this mismatch alone caused the punctuation-only outputs or that the fix improved semantic quality. The previous temperature 0.8-vs-0.7 CPU probe used pre-fix generation input; its result is valid only for that mismatched input format and should not be promoted as a conclusion about corrected-format inference.

## Training/quality evidence (historical, not this hour)
- Latest [Daily 40275426137](https://github.com/mjw3177109/damoxingtest/actions/runs/40275426137): completed/success but **SKIPPED_NO_CHANGES**, no Kaggle submission, zero new optimizer steps. Main latest report directory `reports/2026-10-26/run-40275426137`.
- Daily `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json` read/verified. Daily Artifact `12629319793` exists and is unexpired.
- Historical [GPU Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784) finished; Artifact `12487687305` exists and is unexpired. GPU Tesla T4 14.56 GiB; 3 epochs, 33 optimizer steps, train loss 3.246455, val loss 3.147277, PPL 23.272599, baseline val loss 3.389291, same-run improvement 7.141%. Train/eval 85/24. Historical source training Git SHA unavailable; do not invent.
- Historical fixed greedy samples: **0/10 meaningful**, 10/10 punctuation-only; representative 64 periods. No new generated text this hour. `quality_gate.json`: automatic check false, human review pending, promotion false.
- Run 8 vs Run 12 validation corpora differ; no cross-run best claim.
- Kaggle Kernel `mjw3177109/damoxingtest-gpt-2-daily-training`: live status, version and GPU quota not independently verifiable. Do not infer idle or launch another GPU run.

## Lessons and next bounded experiment
- **Verified lesson:** For BertTokenizerFast, relying on default special-token behavior did materially change actual inference token IDs (10/10, +2). Static source agreement was insufficient; a real pinned tokenizer audit was necessary.
- Existing historical `DataCollatorForLanguageModeling` NameError is absent; `response_only_collator` is still passed to Trainer. No duplicate fix.
- Next: execute a single CPU-only **corrected-format** Run 12 generation with the same pinned base/Adapter/holdout and compare against the archived historical greedy outputs; measure meaningful responses, punctuation-only count, EOS rate and lengths. Preserve both original and corrected inputs' provenance; no automatic promotion. The existing manual-only temperature workflow should not be retriggered automatically.
- Only consider a GPU retrain after model quality evidence, Kaggle quota/state and concurrency checks, approved rollback, and explicit safety gate validation.
- No credentials, tokens, personal data, raw prompts, raw token IDs, or generated private text were added to this audit.
