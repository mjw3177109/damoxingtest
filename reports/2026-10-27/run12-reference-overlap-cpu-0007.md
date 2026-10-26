# Run 12 CPU reference-overlap audit — 2026-10-27 00:07 Asia/Shanghai

## Hypothesis and limits
After correcting prompt tokenization (`add_special_tokens=False`), Run 12 generated non-punctuation text, but semantic quality remained unverified. This experiment tests whether the rejected Run 12 LoRA Adapter improves **character bigram overlap with fixed authored holdout references** relative to the unadapted base model, holding the prompt encoding, decoding, model revision, and evaluation data constant. Character bigram overlap is only a lexical proxy, **not** a semantic accuracy or safety judgment.

## Provenance
- Source GPU training: GitHub Actions `39921870784` (historical completed training; no new GPU training).
- CPU inference workflow: `40355719971` — completed / success; 20 greedy generations (10 fixed prompts × base/candidate).
- Static CI: `40355727624` — completed / success, **261/261** tests.
- Code SHA: `1c241f0da6d79939c18179d1e43ec0ac1b0ef72c` (one-shot workflow); tool `tools/run12_reference_overlap_cpu.py`, tests `tests/test_run12_reference_overlap_cpu.py`.
- Base model: `uer/gpt2-chinese-cluecorpussmall`, revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Rejected Run 12 Adapter SHA-256: `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`.
- Fixed holdout SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.
- Historical training corpus SHA-256: `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`.
- Device: CPU; `max_new_tokens=64`, greedy, `repetition_penalty=1.12`, explicit `add_special_tokens=False`.
- GitHub Actions Artifact: `12665288586`, `run12-reference-overlap-40355719971`, downloaded and parsed.
- `reference_overlap.json` SHA-256: `b9aee03b795e0cc8b6f4b1f9260aa1036980e6c794c6a467b4241e45e91a3494`.

## Actual measurements (not estimates)
| Metric | Base | Run 12 candidate |
|---|---:|---:|
| Fixed prompts | 10 | 10 |
| Mean reference character-bigram F1 | 0.004494 | 0.004494 |
| Nonempty outputs | 10 | 10 |
| At least one CJK character | 10 | 10 |
| Punctuation-only outputs | 0 | 0 |
| EOS stop count | 0 | 1 |
| Verified direct-answer count | not assessed | not assessed |

Candidate minus base lexical proxy = **0.000000**. Only one prompt had nonzero overlap (F1 0.044944) in each arm. Some lengths differed between arms, but this does not establish better meaning or correctness. Raw outputs were intentionally not uploaded to prevent accidental disclosure; therefore human semantic review remains pending.

## Outcome and experience
- **No evidence of improvement on this limited lexical proxy**; no claim of model evolution or self-upgrade.
- This does not prove semantic equivalence: bigram overlap is an imperfect proxy and the sample size is only 10.
- The prior corrected-encoding result (pure punctuation 10/10 → 0/10) is a *generation-format improvement*, not semantic certification.
- Automated CI success and CPU inference completion are not GPU training or model promotion.
- `promotion_approved=false`; PR #70 remains Draft. The previous candidate and archived Adapter remain unchanged and rollback-compatible.
- Kaggle Kernel realtime state/quota was not independently verified; do not start another GPU run.

## Next controlled action
Create a privacy-reviewed **local-only** semantic sample review (no raw prompts, model output, credentials, or personal data in public logs or artifacts), evaluate direct answer relevance, accuracy, refusal/safety, and EOS; then compare against base and Run 12 on identical prompts. If this is impossible in the current authorized environment, explicitly mark the human review blocked. Do not automatically retrain or promote. Keep GPU idle until the quality gate and remote concurrency/quota checks are verified.
