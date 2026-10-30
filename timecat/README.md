# TimeCat verified memory

- identity.json: immutable basic profile, change via reviewed commit.
- goals.json: staged objectives and measurable acceptance criteria.
- core.py + cli.py: standard library SQLite prototype; locally approved memories persist across restarts.
- cloud_memory.py + cloud_cli.py: private SQLite outbox and user-JWT Supabase synchronization; never use a service-role key.
- mentor_context.py: V2.4 fail-closed conversation context; re-reads the authenticated cloud and returns only approved records with provenance. It never falls back to local-only recall.
- private/ (ignored): private memory. Do not publish private conversations to this public repository.
- chronicle/: public, verified engineering history only. Each report needs evidence/run URL, source SHA, timestamp and whether the result is new or reused.
- assets/TimeCat_Official_Mother.png: official user-provided original, SHA-256 recorded in identity.json; binary included in accompanying download package but not yet pushed by the text-only GitHub connector.

Commands:

~~~powershell
python -m unittest discover -s timecat/tests -v
python -m timecat.cli init
python -m timecat.cli status
python -m timecat.cloud_cli context "bobo师傅" --limit 10
~~~

The V2.4 context command requires a valid ordinary-user JWT in the local environment. It does not make ChatGPT scheduled tasks automatically authorized; a separate user-consented connector/gateway is still required.
