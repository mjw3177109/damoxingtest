# Run 12 — Tokenized assistant suffix audit (2026-10-24)

## Hypothesis and source
- Earlier CPU experiment [Run 40064518326](https://github.com/mjw3177109/damoxingtest/actions/runs/40064518326) showed identical generation outcomes when adding a newline after the assistant prefix.
- Hypothesis: the **actual Run 12 tokenizer** maps the production prefix and the newline-suffixed variant to identical input token IDs.
- Rejected GPU training source: [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784).
- Fixed evaluation data SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Rejected adapter weights SHA-256: `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`.
- Audit implementation merged in [PR #38](https://github.com/mjw3177109/damoxingtest/pull/38), main commit `f2bc07e8e194a8bd0011d7c10865f8d031537991`.

## Verification
- Static preflight [Run 40076299500](https://github.com/mjw3177109/damoxingtest/actions/runs/40076299500): `completed/success`.
- Tokenizer-only CPU [Run 40076337028](https://github.com/mjw3177109/damoxingtest/actions/runs/40076337028): `completed/success`; 84/84 repository unit tests passed.
- Retrieved and SHA-256-verified the exact rejected Run 12 adapter before tokenization.
- The produced `audit.json` was downloaded from Artifact `12553023412`, opened and independently inspected.
- Artifact ZIP SHA-256: `460023842c2caa37d5db12713843d998728c4a4e0471f4f1ea55b9817a6548d9`; not expired at verification.
- The tokenizer source recorded in the actual JSON is `rejected_run12_adapter` (not the fallback).
- Real model forward passes: **0**. New GPU training: **no**. Model promotion: **no**.

## Actual results

| Fixed prompt index | Original token count | With trailing newline | Identical input IDs |
| --- | ---: | ---: | --- |
| 0 | 38 | 38 | yes |
| 1 | 41 | 41 | yes |
| 2 | 42 | 42 | yes |
| 3 | 34 | 34 | yes |

**4/4 exact token sequence matches**, verified by SHA-256 comparisons of token-ID arrays. No raw prompt text or token IDs were exported.

## Interpretation and limits
- **Confirmed:** for these four fixed prompts and this exact tokenizer, the trailing newline is tokenization-inert. This explains why the prior single-variable newline experiment produced no change in the model input or output.
- **Not confirmed:** why the rejected LoRA model repeats punctuation/UNK tokens, or whether a genuinely different tokenized prompt would improve useful answers.
- This is an input-contract finding, not evidence of better model quality, safety, or historical-best performance.
- Historical GPU Run 39921870784: Tesla T4 (14.56 GiB), 33 steps, train loss 3.246455, final validation loss 3.147277, PPL 23.272599; **none are new measurements**. Its saved generation quality gate remains 0/10 and promotion remains rejected.
- Prior historical runs used different holdouts; no cross-run best-model ranking is claimed.

## Lessons and next action
1. Before allocating CPU generation or GPU training to a prompt variant, compare its **actual tokenizer input IDs** under the exact model/tokenizer configuration. A textual change may not change any token.
2. Retain negative experiments with code SHA, data/adapter hashes, Run/Artifact IDs, and bounded evidence to avoid repeating ineffective experiments.
3. If exploring another prompt change, pre-register one variant that **provably changes** token IDs, then compare base and rejected candidate with fixed prompts and seeds. Evaluate real answers, not just UNK rate.
4. Keep approved checkpoints, training recipe, quality gate, and safety protections unchanged. Do not submit duplicate Kaggle kernels or disclose credentials.

## Status
- Engineering diagnostic: **verified and archived**.
- Training: **no new training**.
- Model quality: **still failing**.
- Promotion: **rejected**.
