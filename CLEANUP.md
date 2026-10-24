# Cleanup

Baseline inventory for the rules added during static enforcement. These are
**suppressed, not fixed**. New violations fail immediately; removing an entry
is the cleanup signal.

- **Ruff:** 44 explicit `# noqa` directives (37 added in `65acc9c`, 7 already
  present). There are no per-file rule ignores.
- **Import boundaries:** 5 entries in
  `tools/verify/import_boundaries_baseline.json`.
- **Total:** 49 baselined violations.

Checks:

```powershell
uv run ruff check .
uv run python tools/verify/import_boundaries.py
```

Do not add a suppression without adding a row here.

---

## 1. CLI assumes the demo fixture / silent JSON fallback

| File | Line | Rule | Why it is suppressed |
|---|---:|---|---|
| `cli/main.py` | 233 | BLE001 | `json.loads` failure silently falls back to the raw string for replay interventions. |

Cleanup: parse interventions at the CLI boundary and return a usage error for
invalid JSON. Remove the broad catch.

## 2. Explorer has multiple fallback paths

| File | Line | Rule | Why it is suppressed |
|---|---:|---|---|
| `explorer/queries.py` | 78 | BLE001 | Failure-slice construction returns an empty set on any error. |
| `explorer/queries.py` | 258 | BLE001 | AI diagnosis converts any unexpected model-layer error into a 502. |
| `explorer/server.py` | 53 | BLE001 | `importlib.resources` frontend lookup is best-effort. |
| `explorer/server.py` | 165 | SIM105 | `KeyboardInterrupt` shutdown uses `try/except/pass` instead of `contextlib.suppress`. |

Cleanup: resolve the frontend directory once and fail with one explicit error;
replace the shutdown `pass` with `contextlib.suppress(KeyboardInterrupt)`.

## 3. Core library reads the repo fixture

No lint suppression. `core/decision.py:198-203` still opens
`fixture/fixture.json` relative to the checkout. Cleanup: accept fixture data
as an argument or move the loader into the CLI/example layer.

## 4. Duplicated, side-effectful `.env` loading

| File | Line | Rule | Why it is suppressed |
|---|---:|---|---|
| `core/explain.py` | 181 | BLE001 | Unreadable `.env` files are ignored during environment loading. |

Cleanup: one explicit environment loader at the CLI boundary; no library
imports should read `.env`.

## 5. Pytest collection hack

Fixed. `test_fn_from` is now `build_failure_predicate`; the
`__test__ = False` hack was removed.

## 6. Global mutable runtime

No lint suppression. `causality/__init__.py:160-173` still keeps the module
global `_runtime`. Cleanup: pass a runtime/store explicitly, or make `init()`
return a context object.

## 7. SDK append introspection

No lint suppression. `sdk/events.py:96-113` still introspects
`append_with_status` and treats non-Event returns as dropped. Cleanup: make
the `EventLog` protocol explicit and reject non-conforming backends.

## 8. Layering violations

| File | Module imported | Why it is suppressed |
|---|---|---|
| `explorer/loader.py` | `benchmark.opencode.scoring` | `resolve_failure` and `resolve_roles` live in benchmark. |
| `explorer/queries.py` | `benchmark.opencode.scoring` | `score_diagnosis` lives in benchmark. |
| `sdk/tools.py` | `core.provenance` | `capture_tool` lazily records field sources, creating sdk -> core. |

Cleanup: move the three scoring helpers into a shared `core` module; remove
the sdk -> core lazy import by moving provenance recording behind an sdk
callback or into the caller.

## 9. Script-local hacks

No new suppression. `scripts/check-opencode-plugin-compat.py:40-48` still uses
`sys.path.insert` with `# noqa: E402` and a machine-specific AppData fallback.
Cleanup: resolve the plugin path from an argument or environment variable.

## 10. Frontend tests are source-substring checks

No new suppression. `frontend/tests/api_contract.test.ts` still reads source
text and asserts `.includes(...)`. The Playwright smoke test is the first
behavioral browser check. Cleanup: move contract checks to runtime API/UI
assertions.

## 11. Broad catches and simplification debt

All 29 rows below are cleanup candidates, not boundary code.

| File | Line(s) | Rule |
|---|---|---|
| `adapters/langgraph/mapping.py` | 531 | BLE001 |
| `adapters/langgraph/mapping.py` | 668 | SIM102 |
| `adapters/opencode/mapping.py` | 267 | SIM114 |
| `adapters/opencode/mapping.py` | 299 | BLE001 |
| `benchmark/baseline.py` | 220 | SIM105 |
| `benchmark/opencode/runner.py` | 68 | BLE001 |
| `benchmark/opencode/runner.py` | 270 | SIM114 |
| `benchmark/opencode/scoring.py` | 238 | SIM103 |
| `benchmark/opencode/scoring.py` | 375, 389, 440, 477, 538, 560, 601 | BLE001 |
| `core/explain.py` | 311, 319, 366, 382, 493 | BLE001 |
| `core/explain.py` | 325 | SIM102 |
| `core/provenance.py` | 211 | SIM114 |
| `core/replay.py` | 70 | SIM118 |
| `core/validator.py` | 68 | BLE001 |
| `sdk/tools.py` | 145 | SIM108 |
| `storage/sqlite.py` | 99, 161 | SIM117 |
| `tests/test_packaging.py` | 63 | SIM300 |
| `tests/test_phase1.py` | 245 | SIM117 |

Cleanup: replace broad catches with the narrow exceptions each helper can
actually raise; let programming errors propagate. Apply the SIM fixes as a
separate mechanical pass.

## 12. Justified boundary catches and optional imports

These are suppressed because the boundary is intentionally fail-open, or the
test needs the optional driver. They still count as baselines.

| File | Line(s) | Rule / module | Why it is suppressed |
|---|---|---|---|
| `adapters/opencode/server.py` | 32, 61, 89 | BLE001 | Ingest is fail-open by design; telemetry must not break the agent. |
| `explorer/server.py` | 119 | BLE001 | Read-only API converts errors to JSON instead of crashing. |
| `sdk/privacy.py` | 140 | BLE001 | Redaction fallback is intentionally best-effort. |
| `tools/verify/verify.py` | 263, 383 | BLE001 | Verifier reports any failure as evidence instead of crashing. |
| `tests/conftest.py` | 59 | BLE001 | Unreachable PostgreSQL is converted into a test skip. |
| `tests/test_phase2_5.py` | 632 | PGH003 | Monkeypatch helper uses `# type: ignore` with no error code. |
| `tests/test_provenance.py` | 369 | `psycopg` import | Test imports the optional driver after `pytest.importorskip`. |
| `tests/test_postgres_integration.py` | 271 | `psycopg.types.json` | Integration test imports `Jsonb` after `pytest.importorskip`. |

Cleanup: keep the fail-open boundaries, but document the exception in code.
For tests, add a small helper in `storage/_psycopg.py` that returns the module
or skips; then remove the direct imports and both psycopg baseline entries.

## 13. Duplicated artifacts

No baseline. Static assets now have `scripts/sync-explorer-static.py --check`
in verify, and the local OpenCode plugin copy has
`scripts/sync-opencode-plugin.py --check`. The plugin check skips when
`.opencode/` is absent (CI), and verifies bytes when installed locally.
