# Run 12 — Direct-answer instruction paired CPU generation (2026-10-24)

## Hypothesis and provenance
- Hypothesis: inserting exactly one direct-answer instruction before the assistant delimiter may reduce punctuation/UNK degeneration and improve the rejected Run 12 candidate's actual responses.
- The prior [tokenization audit Run 40084814850](https://github.com/mjw3177109/damoxingtest/actions/runs/40084814850) verified that all four fixed holdout prompts change their token sequences (+13 tokens each).
- Controlled generation: [GitHub Actions Run 40088294558](https://github.com/mjw3177109/damoxingtest/actions/runs/40088294558), **completed/success**; workflow head SHA \`9d2138f86549cf9fa76b969e7c84eb66be70a5fb\`; [PR #42](https://github.com/mjw3177109/damoxingtest/pull/42) merged after [static preflight Run 40088243005](https://github.com/mjw3177109/damoxingtest/actions/runs/40088243005) succeeded with **98/98 tests**.
- Rejected source GPU training: [Run 39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Adapter SHA-256 \`979a0410327cd191b6dceace4ac0985c81fdc4448c3e200aea9d5803c8036d7c\`.
- Fixed evaluation data SHA-256 \`5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f\`; base model revision \`c2c0249d8a2731f269414cc3b22dff021f8e07a3\`.
- Fixed inference: **CPU**, greedy decoding, 64 maximum new tokens, repetition penalty 1.12, seed \`42 + prompt_index\`, \`token_type_ids\` removed to match training. No new training.
- Original ZIP Artifact **12558400090** (\`run12-direct-answer-generation-40088294558\`), downloaded and opened; ZIP SHA-256 \`7d1f4fd7c64ec6f107fd833fa01808a6b5ac4154f732454c280266fdd8e26096\`. Contains \`review.json\` with **16/16** generation rows, only filtered output excerpts and aggregate diagnostics.

## Actual matched results

| Metric (4 prompts per cell) | Base / original | Base / direct-answer | Rejected LoRA / original | Rejected LoRA / direct-answer |
| --- | ---: | ---: | ---: | ---: |
| Punctuation-only answers | 0 | **3** | 2 | **3** |
| Blank answers | 0 | 0 | 1 | 0 |
| Contains Chinese | 4 | 1 | 1 | 1 |
| EOS termination | 1 | 0 | 1 | 1 |
| UNK-only generations | 0 | 0 | 1 | 0 |
| Mean longest identical-character run | 1.25 | 48.25 | 32.25 | 48.25 |

The original controls **reproduced** the prior CPU readability audit's punctuation counts (base 0/4, candidate 2/4). This strengthens within-setup comparability.

The direct-answer variant **worsened punctuation-only generation**: base 0/4 → 3/4, candidate 2/4 → 3/4. It removed the one candidate UNK-only blank in this small sample, but replaced it with an unrelated answer, not a useful direct answer. No improvement in actual answer quality is established.

## Filtered output examples
- Candidate, original prompt index 0: \`................................................................\`
- Candidate, direct-answer prompt index 0: \`................................................................\`
- Candidate, original prompt index 3: empty output (64 UNK tokens).
- Candidate, direct-answer prompt index 3: \`函 数 的 返 回 值 是 否 可 以 被 确 认 为 已 经 确 认 的 数 据 ？ （ 如 果 确 认 了 ， 请 先 确 认 ）\` — not a direct answer to the original question.

All excerpts were passed through the existing privacy filter; the artifact does not export raw prompt text or token ID sequences. The small four-prompt sample is a diagnostic, **not a quality/safety certification**.

## Training and quality gate
- **This run:** 16 CPU generations, 0 GPU optimizer steps, no new Train Loss / Val Loss / PPL, no new model checkpoint, no Kaggle Kernel submission.
- **Historical Run 12:** Tesla T4 14.56 GiB, 33 optimizer steps, Train Loss 3.246455, Val Loss 3.147277, PPL 23.272599; historical quality gate **0/10**, \`promotion_approved=false\`.
- **Latest Daily Run 40065584092:** \`SKIPPED_NO_CHANGES\`; reused historical evidence and performed 0 new training steps.
- Older Run 8 used a different validation set; cross-run historical-best improvement cannot be inferred.

## Root-cause status and next bounded action
1. This single prompt-only intervention is **rejected**. Do not repeat it or promote a checkpoint.
2. The prompt change is genuinely token-changing but makes punctuation degeneration worse; changing tokenization alone is insufficient and may introduce new failure modes.
3. A next **CPU-only**, preregistered diagnosis should compare the first-step logits/ranks of punctuation, UNK and EOS under original vs changed prompt, on the same four fixed prompts and both models, without a GPU training run.
4. If any code defect is identified, fix it minimally, run static checks/unit tests and verify the input/label contract before proposing a new training recipe. Keep the previously approved checkpoint untouched.
5. Kaggle real-time status was not independently available; historical \`COMPLETE\` is not evidence of new training. No credentials or personal information were committed.

**Decision:** Experiment completed; **negative quality result**; candidate **not promoted**; preserve this failed experiment and its evidence.
