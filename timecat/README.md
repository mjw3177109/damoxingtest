# TimeCat verified memory
- `identity.json`: immutable basic profile, change via reviewed commit.
- `goals.json`: staged objectives and measurable acceptance criteria.
- `core.py` + `cli.py`: standard library SQLite prototype; locally approved memories persist across restarts.
- `private/` (ignored): private memory. Do not publish private conversations to this public repository.
- `chronicle/`: public, verified engineering history only. Each report needs evidence/run URL, source SHA, timestamp and whether the result is new or reused.
- `assets/TimeCat_Official_Mother.png`: official user-provided original, SHA-256 recorded in `identity.json`; binary included in accompanying download package but not yet pushed by the text-only GitHub connector.

Commands: `python -m unittest discover -s timecat/tests -v`, `python -m timecat.cli init`, `python -m timecat.cli status`.
