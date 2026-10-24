# Run 12 — Token-changing direct-answer prompt audit (2026-10-24)

## Hypothesis and source
- Prior [CPU Run 40076337028](https://github.com/mjw3177109/damoxingtest/actions/runs/40076337028) established that adding a trailing newline changed **0/4** fixed prompt token sequences. That negative experiment is retained.
- One pre-registered variant inserts the directive “请直接回答，不要复述问题。” in the user turn immediately before the existing assistant delimiter. The production prompt and training recipe remain unchanged.
- Rejected GPU training source: [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784). The exact rejected adapter SHA-256 is `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`.
- Fixed evaluation data SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`. Base model revision: `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.

## Verified engineering and test evidence
- [PR #41](https://github.com/mjw3177109/damoxingtest/pull/41) merged as `52c463d830f54094c2dfec6881460eef0894d9d2`; only the CPU audit tool, five offline tests, and a read-only workflow were added.
- Five new offline unit tests passed locally. [Static preflight Run 40084710405](https://github.com/mjw3177109/damoxingtest/actions/runs/40084710405) completed successfully.
- [CPU tokenizer Run 40084814850](https://github.com/mjw3177109/damoxingtest/actions/runs/40084814850) completed successfully and uploaded Artifact **12556531644**, `run12-tokenized-direct-answer-40084814850`.
- The actual Artifact ZIP was downloaded, opened, and its `audit.json` independently inspected. ZIP SHA-256: `8a215b449e505c3ffeee830ab0704086859e7bc51c4963a085f736ced32374d3`.
- The exact rejected adapter and its saved tokenizer were used; no base-tokenizer fallback. No raw prompt text or token ID sequence was exported.

## Actual measured results

| Fixed prompt index | Original token count | Direct-answer variant | Token sequence changed |
| --- | ---: | ---: | --- |
| 0 | 38 | 51 | yes |
| 1 | 41 | 54 | yes |
| 2 | 42 | 55 | yes |
| 3 | 34 | 47 | yes |

**4/4 actual token sequences changed; +13 tokens each.** This is a tokenization-contract finding only, not a language-model improvement.

## GPU, generation and promotion boundaries
- **This run:** CPU tokenizer audit only; **0 model forward passes**, **0 GPU training steps**, no new Train Loss/Val Loss/PPL, no new generated answers, no model promotion.
- **Historical Run 12:** Tesla T4 (14.56 GiB), 33 optimizer steps, train loss 3.246455, validation loss 3.147277, PPL 23.272599; quality gate 0/10 and promotion rejected.
- Earlier historical Run 8 used a different validation set; no claim of cross-run best-model superiority.
- Current latest Daily Run 40065584092 reused historical metrics and performed 0 new steps. Kaggle real-time state was not independently verified.

## Lessons, limitations and next controlled experiment
1. Textual prompt edits must be checked against the exact tokenizer before spending inference or GPU compute. A trailing newline was inert; this one bounded directive is not.
2. Token-sequence change does **not** imply a more readable, safe or correct answer. The cause of punctuation/UNK degeneration remains unresolved.
3. Next, if authorized compute is available, run **paired bounded CPU generations** on the same four fixed prompts for base and rejected candidate with control versus this single variant. Keep seeds, decoding, Adapter and holdout fixed. Record punctuation-only, UNK, EOS, blank outputs and privacy-filtered answer excerpts; compare to prior matched controls and preserve failures.
4. No production prompt, training data, training recipe, model weights, quality gate, secrets or approved checkpoint were changed. Do not launch a duplicate Kaggle GPU run or promote the rejected candidate.

## Status
- Engineering experiment: **completed and verified**.
- Model quality improvement: **not measured**.
- Training: **no new GPU training**.
- Promotion: **rejected**.
