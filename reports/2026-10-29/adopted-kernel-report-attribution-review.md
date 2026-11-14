# 2026-10-29 05:04 CST — Adopted Kaggle kernel reporting provenance audit

## Scope and verified evidence
- Repository: `mjw3177109/damoxingtest`. This change is isolated to Draft PR #72; production `main` remained `361fa9ca36528eea70a7fea2d606c1bab50e24b8`.
- Latest production Daily GitHub Run: [40457573324](https://github.com/mjw3177109/damoxingtest/actions/runs/40457573324), `completed/success` with `SKIPPED_NO_CHANGES`, not fresh GPU training. Report: `reports/2026-10-27/run-40457573324/`.
- Historical GPU Run: [39921870784](https://github.com/mjw3177109/damoxingtest/actions/runs/39921870784), Tesla T4 14.56 GiB, 3 epochs, 33 optimizer steps, train loss 3.2464554598837188, final eval loss 3.1472766399383545, PPL 23.272598534340947. Historical samples 0/10 meaningful, human review pending; no promotion.
- Historical data SHA-256: train `ad2dfcb5f4549981d555b570e255f54b98c7162c52d46f72af147dc3a035847c`; evaluation `5d0c93dc919767bd9bb19729b8eecb68bbfd557d9ee1376e12f8aba072bff41f`; recipe `34b77ea554cbdd07a1fd54c1443734b2d963f4f991211d606cc2b88a650e4ba0`.
- Kaggle Kernel: `mjw3177109/damoxingtest-gpt-2-daily-training`. Live status, concurrent use and remaining GPU quota were **not independently verified**; no new push attempted.

## Root cause and minimal remediation
`scripts/finalize_report.py` correctly blocked final status `KAGGLE_EXISTING_KERNEL_REVIEW_REQUIRED` but still trusted a downloaded remote `training_status.json` to choose its narrative. A remote `skipped_no_changes=true` falsely described this GitHub run as having skipped its own training, while `skipped_no_changes=false` could display remote metrics as **this run's results** and describe a fresh validation-loss improvement. This is a deterministic offline reporting bug, not evidence of an actual misattributed production run.

Commits in Draft PR #72:
- `840f19e9cfc830ef4b679a3de9eb24c56f2b4220`: explicit source-unverified narrative precedence.
- `d6374f0bc073c3c7d404570dd539439cf6f50560`: regression assertions against misleading skip claims.
- `9d984caaa3cbdaefe289d67850a02ad03d312f15`: treat adopted-kernel outputs as unverified irrespective of remote skip flag; do not present their metrics as current.
- `705f5fa33e18fe13721fa1400ef6f87e98277e04`: add non-skipped remote-output regression.
- `aedfe9a1eb62cc6da6900e89e856caad6a9228bc`: correct escaped newline fixtures after reading CI failure.

## Tests and failures
- Intermediate [CI Run 40768624585](https://github.com/mjw3177109/damoxingtest/actions/runs/40768624585) failed 1/202 tests because a newly added test fixture wrote a literal `\\n` rather than a newline; the error was verified in original job logs and corrected without GPU work.
- Final [CI Run 40768661756](https://github.com/mjw3177109/damoxingtest/actions/runs/40768661756), Job `123099572700`: **completed/success**, **202/202** tests, Ruff F821 and response-only `-100` masking checks passed.
- Tests are CPU-only/offline. No Kaggle kernel run, fresh training, new model sample, new loss/PPL measurement or model promotion is claimed.

## Artifact and quality audit
- Main Daily report files verified: `training.log`, `metrics.json`, `samples.json`, `report.md`, `run_metadata.json`, `training_status.json`, `quality_gate.json`.
- Verified unexpired GitHub artifacts: Daily `12713006845`, historical GPU `12487687305`, CPU EOS audit `12696138797`.
- Latest Daily is a pre-submission skip. Its metrics and samples are explicitly historical, not newly measured. `promotion_approved=false`.
- Run 8 and Run 12 used different validation sets; no cross-run best-model claim is justified.

## Lessons, rollback and next experiment
An external Kernel's `COMPLETE` or `skipped_no_changes` metadata cannot establish provenance for the current GitHub Run. Final status and every report heading/narrative must fail closed and consistently label unknown-origin outputs. Test both skip=true and skip=false responses; validate fixture escaping in CI.

Retain Draft PR #72 and PR #73 unmerged. Prior Draft head `479f47168e297e55f0773efe44601fd60aade3b4` is a rollback reference. No production rollback needed. Independently verify Kaggle remote state/quota and review combined workflow before any GPU experiment. Next safe experiment: CPU-only fixed-weight paired generation using Run 12 adapter, fixed prompts and deterministic decoding, with aggregate repetition and meaningful-answer rates; never claim improvement without comparable metrics and independent review.

No credentials, personal data or sensitive model outputs are included.
