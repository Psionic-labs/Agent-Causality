# Feature Map

How each user-facing feature is reached, where it lives, and whether the
deterministic verifier exercises it.

Run `uv run python tools/verify/verify.py` for every check.
`uv run python tools/verify/verify.py --quick` skips the frontend build, the static sync check, the Explorer server, and Playwright.
Evidence is written under `tools/verify/artifacts/<run>/`.

Legend: **covered** = exercised by the verify CLI; **partial** = some path is
exercised; **not covered** = only unit tests or no automated end-to-end check.

| Feature | How a user reaches it | Entry point and key files | Verify coverage |
|---|---|---|---|
| SDK capture | `causality.init(db)`, then `@causality.agent`, `@causality.merge_decision`, capture decorators | `causality/__init__.py`, `sdk/events.py`, `sdk/lifecycle.py`, `sdk/tools.py` | **not covered** — unit tests only |
| CLI analysis | `uv run causality --fixture fixture/fixture.json <command>` or `--db PATH` | `cli/main.py`; `core/slicing.py`, `core/replay.py`, `core/explain.py`, `core/reducer.py` | **partial** — `agents` is exercised; `slice`, `why`, `reconstruct`, `provenance`, `replay`, `interaction`, `minimize` are not |
| Offline explanation | `uv run causality ... explain --no-llm`; also the demo example | `core/explain.py`, `core/replay.py` | **partial** — offline explanation runs in the example flow, not through the CLI |
| Runnable example | `uv run python examples/customer_approval.py` | `examples/customer_approval.py` | **covered** |
| Explorer demo UI | `uv run python -m explorer.server` then open `http://127.0.0.1:8766/` | `frontend/app/page.tsx`, `frontend/components/*`, `frontend/lib/*`; served by `explorer/server.py` | **partial** — Playwright checks load, graph, node selection, timeline, metrics and evidence tabs; filters, session picker, reset, keyboard navigation and AI diagnosis are not covered |
| Explorer read API | `GET /api/overview`, `/api/failure`, `/api/diagnosis`, `/api/evidence`, `/api/event?id=`, `/api/ai-diagnosis` | `explorer/server.py`, `explorer/queries.py`, `explorer/loader.py` | **partial** — all endpoints except `/api/ai-diagnosis` are asserted |
| Live SQLite Explorer | `uv run python -m explorer.server --db .causality/events.db` or `causality-explorer --db ...` | `explorer/loader.py`, `storage/sqlite.py` | **not covered** — verify uses the bundled demo dataset only |
| OpenCode ingest receiver | `uv run causality-opencode-ingest --db .causality/opencode.db`, then POST `/v1/opencode/events` | `adapters/opencode/server.py`, `adapters/opencode/mapping.py` | **not covered** — no live POST → SQLite → Explorer round trip |
| OpenCode plugin | Install `@psionic-labs/opencode-agent-causality`; OpenCode posts events automatically | `packages/opencode-agent-causality/src/index.ts` | **partial** — unit tests and typecheck run; no receiver integration |
| LangGraph adapter | `CausalityCallbackHandler(store)`; pass `handler.config()` to `graph.invoke` | `adapters/langgraph/mapping.py`, `examples/replit_incident.py` | **not covered** |
| Benchmarks | `uv run causality-benchmark ...` | `benchmark/runner.py`, `benchmark/scenarios.py`, `benchmark/scoring.py` | **not covered** — long-running and provider-dependent |
| Postgres storage | Set `DATABASE_URL`; use the CLI or Explorer | `storage/postgres.py` | **partial** — CI job runs integration tests; local verify does not |
| Redaction / privacy | Automatic on capture and ingest | `sdk/privacy.py`, `adapters/redaction.py` | **not covered** — unit tests only |
| Frontend build and vendored assets | `npm run build`, then `scripts/sync-explorer-static.py` | `frontend/`, `explorer/static/` | **covered** — build and sync check run in verify |

## Known gaps to close next

1. Ingest receiver: start the server, POST a minimal OpenCode event, assert
   `202`, then query the resulting SQLite trace through `/api/overview`.
2. Live Explorer: seed a temporary SQLite database and exercise `--db`.
3. CLI: add one assertion per analysis command against the fixture.
4. Explorer UI: cover the session picker, event-type filters, reset, and
   `/api/ai-diagnosis` opt-in behavior.
5. LangGraph: run `examples/replit_incident.py` and assert its event count.
