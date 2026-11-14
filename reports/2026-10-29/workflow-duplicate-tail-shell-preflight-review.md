# 2026-10-29 03:05 CST — Kaggle workflow duplicate-tail incident and preventive CI

## Scope, evidence, and hypothesis

- Repository: `mjw3177109/damoxingtest`; production `main` remains `361fa9ca36528eea70a7fea2d606c1bab50e24b8`.
- Draft PR #72 had head `42011b111c85eb5999fd9015a1c49fe988d36d67` before this fix.
- The 535-line draft `.github/workflows/daily-gpt2-training.yml` contained a malformed `fi; then` followed by an accidentally duplicated tail of the Kaggle polling, quality-gate, upload, and report-sync logic. Three named workflow steps occurred twice.
- Earlier static CI Run `40741744181` was green with 198 Python tests, but did **not** shell-parse the production workflow. This is a confirmed static validation gap, **not** a demonstrated Kaggle incident.

## Root cause and minimal remediation

1. `12ea0c611a34dce5e722c267dfc7c47aebfb4f37`: remove the malformed duplicate tail; retain the original, single quality-gate, artifact-upload, and report-finalization steps. Workflow reduced from 535 to 374 lines.
2. `429e231e563f465c25db9bd9ee4c00f98c78c872`: add offline test checking unique step names and running `bash -n` against embedded Bash blocks.
3. `2835446edbce290741d6c0f84ffe3fb31234495f`: include changes to the production workflow path in static preflight PR triggers.
4. Initial test regex incorrectly double-escaped whitespace; CI Runs `40751125103` and `40751138827` failed with 2 tests (`0` Bash blocks/step names detected). Fixed in `d316fd74438accb0ff59a4b359346bb5ea9e4bd5`.

## Verification and safety gates

- GitHub Actions static preflight Run `40751170884`: **completed / success**, 200/200 tests passed; both new shell/step-uniqueness tests passed. Ruff F821 and response-only collator/`-100` checks passed.
- No Kaggle push, training restart, GPU quota use, model promotion, or production main-branch update was performed by this remediation.
- PR #72 and #73 remain draft and require review. The static test is a syntax/structure gate, **not** a live Kaggle, semantic-quality, or full workflow execution proof.

## Historical model evidence (NOT new results)

- Latest main-branch Daily Run `40457573324` (2026-10-27 UTC): `SKIPPED_NO_CHANGES`, no GPU training, reused artifacts.
- Historical GPU Run `39921870784` (2026-10-23 UTC): Tesla T4 14.56 GiB, 3 epochs, 33 steps, train loss 3.246455, final validation loss 3.147277, PPL 23.272599; train corpus SHA-256 `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`, eval corpus SHA-256 `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`, recipe SHA-256 `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Historical sample quality: 0/10 meaningful, mostly punctuation loops; human review pending, promotion disallowed. Historical Run 8 and Run 12 validation datasets differ; no comparable historical-best improvement is claimed.
- Main latest report: `reports/2026-10-27/run-40457573324/`, containing `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, and `quality_gate.json`.
- Artifacts checked: Daily `12713006845`, GPU `12487687305`, CPU audit `12696138797` (all unexpired at audit time).
- Kaggle remote kernel status, remaining quota and concurrent use were **not independently verified**. No new training or generated samples are claimed.

## Lesson and next controlled action

A green Python CI is insufficient for shell-heavy workflow edits. Require unique step structure, Bash syntax, and a workflow-path CI trigger before reviewing any future Kaggle submission changes. Next: independently review PR #72/#73, verify remote Kaggle status/quota before any GPU activity, and perform CPU-only fixed-weight paired generation diagnostics for punctuation repetition, valid-answer rate and short-answer rate. Keep all credentials and personal data out of reports.
