# Agent Guide

## Setup

- `uv sync`
- `npm ci --prefix frontend`
- `npm ci --prefix packages/opencode-agent-causality`
- `npx --prefix frontend playwright install chromium`

## Verify

- After every edit: `uv run python tools/verify/verify.py --quick`
- Before finishing: `uv run python tools/verify/verify.py`
- Both print PASS/FAIL, timings, and artifact paths under `tools/verify/artifacts/`.
- Never claim done without the full PASS/FAIL summary.

## Architecture rules

- Layering: `sdk -> core -> storage/adapters -> explorer/cli`; `explorer` must not import `benchmark`.
- Import boundaries: `uv run python tools/verify/import_boundaries.py`.
- Postgres: use `storage._psycopg.load_psycopg` / `load_jsonb`; no direct `psycopg` imports.
- Suppressions are budgeted at 49 in `CLEANUP.md`. A new `# noqa` or `type: ignore`
  needs a CLEANUP row; `uv run python tools/verify/suppression_budget.py` enforces it.

## Generated files

- `explorer/static/` is generated from `frontend/`. Never edit it. Run
  `cd frontend && npm run build`, then `uv run python scripts/sync-explorer-static.py`.
- `.opencode/plugins/agent-causality.ts` is generated from
  `packages/opencode-agent-causality/src/index.ts`. Never edit it. Run
  `uv run python scripts/sync-opencode-plugin.py`.

## Blessed patterns

- New CLI command: parser and handler in `cli/main.py`; logic in `core/`; pytest coverage.
- New Explorer endpoint: query in `explorer/queries.py`; route in `explorer/server.py`;
  assertion in `tools/verify/verify.py`.
- New UI: component in `frontend/components/`; data through `frontend/lib/api.ts`;
  Playwright assertion; build and sync.
- Capture: use `sdk/events.py` `Event` and `EventLog`; no runtime introspection of append returns.
- Optional Postgres: use `storage/_psycopg.py`.
- Tests: pytest for Python, `node:test` for frontend; assert behavior, not source text.

## Don'ts

- Don't hardcode fixture decision IDs or fall back to bundled fixtures.
- Don't add fallback filesystem paths or broad `except Exception` at internal boundaries.
- Don't add `# noqa` or `type: ignore` without a CLEANUP.md row.
- Don't edit generated files or commit `tools/verify/artifacts/`.
- Don't use `phase N` in commit messages; describe the change.

For non-trivial work, invoke the `poteto-mode` skill.
