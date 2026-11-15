# 2026-10-29 03:59 CST — Existing Kaggle kernel provenance guard

## Evidence and failure hypothesis

- Repository: `mjw3177109/damoxingtest`; production `main` remained `361fa9ca36528eea70a7fea2d606c1bab50e24b8` during this review.
- Draft PR #72 previously treated an already-RUNNING/QUEUED/PENDING canonical Kaggle kernel as the current run's output once it reached COMPLETE. It intentionally avoided duplicate `kaggle kernels push`, but it did **not** prove that the remote job's code/data/recipe matched the new GitHub run.
- `scripts/finalize_report.py` previously classified `status.txt=COMPLETE` plus `training_status.status=completed` and any nonempty `metrics.json` as SUCCESS. Thus stale or unrelated remote outputs could be misattributed as a fresh run. This is a source-confirmed **provenance risk**, not evidence that an actual Kaggle run was misattributed.
- Current main Daily Run `40457573324` (2026-10-27 UTC) is `SKIPPED_NO_CHANGES`, not fresh training. Remote Kaggle status, quota and concurrency were not independently verified.

## Minimal draft-branch remediation

1. `af8c78188d94e0b1c18db7ae1c21b9b95626ca78`: track whether an already-active remote kernel was adopted. Continue monitoring and retrieving its output without duplicate push, but if it reaches COMPLETE, mark `KAGGLE_EXISTING_KERNEL_REVIEW_REQUIRED` rather than treating it as fresh training.
2. `8bc862748aacb263498d8eafbaaaa73d191a6393`: give this review-required status explicit precedence in `finalize_report.py`, even if a downloaded `training_status.json` misleadingly claims `skipped_no_changes`.
3. `c9f347d99f4237787e9aa0f0e80e25dae100510e`: update active-kernel fake-CLI regression and add a report finalization test with completed/reused-looking metrics, asserting no SUCCESS or SKIPPED_NO_CHANGES classification.

## Tests, incidents, and promotion

- Intermediate CI Runs `40759115846` and `40759119932` failed because the first code-only commits intentionally preceded the matching test updates. These were static CI failures, not Kaggle failures.
- Final static CI Run `40759143716` / Job `123066026851`: **completed/success**, 201/201 Python tests passed; targeted active-kernel and report-finalization tests passed. Static Ruff F821 and response-only collator checks ran.
- This is offline/fake-CLI evidence only. No new Kaggle kernel push, GPU training, generated samples, quality improvement, or model promotion was performed. PR #72 remains Draft; `main` unchanged.

## Historical training baseline (not new)

- Historical Run `39921870784` on 2026-10-23: Tesla T4 14.56 GiB, 3 epochs, 33 optimizer steps, train loss 3.246455, validation loss 3.147277, PPL 23.272599.
- Train data SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; fixed eval data SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; recipe SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Fixed historical sample quality 0/10 meaningful, human review pending, promotion not approved. Run 8 and Run 12 used different validation sets; no cross-run historical-best claim is justified.
- Latest Daily report files verified: `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json`. Artifacts verified unexpired: Daily `12713006845`, GPU `12487687305`, CPU audit `12696138797`.

## Lesson, rollback, and next step

Do not equate observing an already-active remote kernel's COMPLETE with training on the current GitHub commit. Preserve downloaded output for audit, fail closed, and require a separately verifiable code/data/recipe provenance contract before any future attribution. Rollback is the prior Draft PR #72 head `c0a39e1ff36f028539f1ed9318b09fd90f926cdf`; no production rollback needed. Next: independent PR review and remote Kaggle quota/status verification, then CPU-only fixed-weight paired generation diagnostics. Never commit credentials, personal data, or fabricated metrics.
