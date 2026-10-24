# Run 12 punctuation-feedback CPU experiment — protocol and preflight (2026-10-24)

## Status and provenance
- GitHub PR: #47 (merged; CPU diagnostic only).
- Code SHA (squash merge): `c393165b51dcf2193474f894672273520deea303`.
- Static preflight: Actions Run `40100693055`, completed/success; **110/110 offline tests passed**; Python compile, Ruff F821 and response-only collator contract checks passed.
- CPU experiment: Actions Run `40100735421`; launched by merge, **result pending at time of this protocol**. A queued/running Actions status is not an experiment result.
- Source GPU training: Run `39921870784` (rejected candidate, 33 steps); no new GPU training in this change.
- Base model: `uer/gpt2-chinese-cluecorpussmall`, pinned revision `c2c0249d8a2731f269414cc3b22dff021f8e07a3`.
- Rejected LoRA adapter SHA-256: `979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c`.
- Fixed holdout SHA-256: `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`.

## Hypothesis
The rejected LoRA may amplify punctuation self-feedback after a period is present in the token history. Earlier first-step diagnostics cannot distinguish this from the base model's own repetition tendency.

## Controlled experiment
On four pinned prompts, compare base model and rejected LoRA under **identical** histories containing 0, 1, 2 or 3 forced period tokens. Run exactly 32 CPU forward passes (16 matched pairs), using the pinned tokenizer, the same model revision, `repetition_penalty=1.12` and no `token_type_ids`. Record category probabilities/ranks for punctuation, UNK and EOS, but not raw token IDs, prompt text, logits or sensitive content. Refuse mismatched histories or unpinned adapter data. No training, model updates, Kaggle submission, or promotion.

## Acceptance / comparison
The experiment is complete only when the CPU run has a non-expired downloadable Artifact containing a validated `review.json` with 32 rows, 16 matched pairs, and no promotion. Compare punctuation Top1 counts by forced-prefix length between base and candidate and against first-step Run `40092707377`. These are **diagnostic metrics, not Train Loss / Val Loss / PPL or answer-quality scores**. Do not claim improvement or causal proof from a forced-prefix result. A failure or incomplete Artifact must be recorded as failure, not as success.

## Existing training evidence (unchanged)
Source Run 12: Tesla T4 14.56 GiB, 33 steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; fixed generation gate 0/10, promotion rejected. The previous Daily Run `40065584092` was `SKIPPED_NO_CHANGES` (0 new training steps). Its metrics are historical reuse, not fresh measurements. Historical Run 8 and Run 12 used different evaluation sets, so their validation losses do not establish a cross-run best.

## Failure lessons and next action
Prior direct-answer prompting increased punctuation-only outputs, despite lower average punctuation probability. A category's total probability and the Top1 token can move in opposite directions. Forced-prefix measurements should test feedback separately from initial-token selection. After CPU Artifact verification, archive actual results, error logs and comparison in a separate auditable report; if no interpretable improvement, do not change training recipes or consume GPU. Keep the previously approved checkpoint untouched.

## Safety
Protect users and humanity. Minimal read-only Actions permissions for the CPU audit; no credential, personal data or raw token IDs in the report. Never bypass the quality gate.
