# GPT-2 skipped-run reporting provenance fix (2026-10-24)

## Evidence and hypothesis
- Latest scheduled Daily GPT-2 T4 Training: [Run 40065584092](https://github.com/mjw3177109/damoxingtest/actions/runs/40065584092), `completed/success` at 2026-10-24 05:17 UTC.
- Kaggle CLI observed `QUEUED -> COMPLETE` for kernel `mjw3177109/damoxingtest-gpt-2-daily-training` version 8. The Kaggle notebook returned `skipped_no_changes=true` and `current_run_performed_gpu_training=false`.
- `training.log` explicitly said no new training; `metrics.json` recorded `train_steps=0`, `train_loss=null`, `gpu_name=null`, and reused evidence from `reports/2026-10-23/run-39921870784`.
- Nonetheless, the report phrased reused validation loss as a current-run improvement, and a copied `stages/stage3_lora_training.md` claimed an Adapter was saved during this run. Hypothesis: the report generator copied historical stages and evaluated historical metrics without a skipped-run provenance branch.

## Minimal fix
- [PR #37](https://github.com/mjw3177109/damoxingtest/pull/37) merged as `c4ea415d9a08b8da0211ebcd0401446d967d689a`.
- `scripts/finalize_report.py`: explicitly label reused metrics, samples, GPU, runtime and stage provenance; omit historical stage markdown from the new run root when training was skipped.
- `.github/workflows/daily-gpt2-training.yml`: exclude report-only changes to `scripts/finalize_report.py` from the push trigger, preventing an unnecessary Kaggle kernel submission.
- `tests/test_finalize_report_skip.py`: synthetic skipped-run and real completed-run regression cases. No training recipe, Adapter, data, safety gate, or credentials changed.

## Verification
- Static Preflight [Run 40072580051](https://github.com/mjw3177109/damoxingtest/actions/runs/40072580051): `completed/success` on PR head `418ace9eb6540fcd9f51f7474f89a6b8293de29b`. CI ran repository unit tests, compilation, Ruff F821, and response-only collator contract checks.
- Post-merge main SHA `c4ea415d9a08b8da0211ebcd0401446d967d689a` confirmed; patched script and workflow path exclusion verified.
- No new Daily GPU workflow run was present in the latest Actions listing at post-merge check. This is a point-in-time observation, not a permanent guarantee.

## Training and quality evidence (historical only)
- Historical source Run `39921870784`: Tesla T4, 14.56 GiB, 33 training steps, train loss 3.246455, final val loss 3.147277, PPL 23.272599. These are **not** new measurements from Run 40065584092.
- Latest skipped run quality gate: `promotion_approved=false`, 0/10 meaningful generation samples; candidate was not promoted. No new generated answer.
- Historical best comparison remains inconclusive because validation datasets differed across runs.

## Decision, lesson, and next step
- **Decision:** report-only patch accepted; **model promotion rejected**; no new GPU training started.
- **Lesson:** a successful Actions run, Kaggle `COMPLETE`, or copied stage files do not establish that training occurred. Always use `training_status.json`, `train_steps`, original run metadata, and quality gate to distinguish current work from reused evidence.
- **Next:** investigate Run 12's UNK-token generation degeneration with controlled CPU diagnostics. Keep approved checkpoints unchanged, avoid duplicate Kaggle submissions, and verify actual response quality before a training or promotion decision.
- **Safety:** no tokens, keys, private user data, or protected safeguards were altered or logged.
