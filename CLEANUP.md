# Cleanup

Baseline inventory for the rules added during static enforcement. These are
**suppressed, not fixed**. New violations fail immediately; removing an entry
is the cleanup signal.

- **Ruff:** 44 explicit `# noqa` directives (37 added in `65acc9c`, 7 already
  present). There are no per-file rule ignores.
- **Import boundaries:** 0 entries in
  `tools/verify/import_boundaries_baseline.json`.
- **Total:** computed from the tables below by
  `tools/verify/suppression_budget.py`; never hand-edit a total.

Checks:

```powershell
uv run ruff check .
uv run python tools/verify/import_boundaries.py
```

Do not add a suppression without adding a row here.

---

## 1. CLI assumes the demo fixture / silent JSON fallback

Fixed. Replay intervention values are parsed at the CLI boundary. JSON
literals stay JSON, a bare identifier is a string, and other text is a
usage error.

## 2. Explorer has multiple fallback paths

Fixed. The frontend directory is ``explorer/static`` next to the server
module, and ``main`` exits when ``index.html`` is missing. Shutdown uses
``contextlib.suppress(KeyboardInterrupt)``. A missing failure event yields
an empty slice. Model transport failures are ``RuntimeError`` from
``explain`` and stay HTTP 502. Other errors propagate.

## 3. Core library reads the repo fixture

Fixed. ``create_fixture_decision`` takes the loaded fixture document.
Callers open the file.

## 4. Duplicated, side-effectful `.env` loading

Fixed. ``sdk.env.load_env_file`` reads the current directory's ``.env``.
The causality CLI and the explorer entry point call it. ``explain`` does not.

## 5. Pytest collection hack

Fixed. `test_fn_from` is now `build_failure_predicate`; the
`__test__ = False` hack was removed.

## 6. Global mutable runtime

No lint suppression. `causality/__init__.py:160-173` still keeps the module
global `_runtime`. Cleanup: pass a runtime/store explicitly, or make `init()`
return a context object.

## 7. SDK append introspection

Fixed. ``AppendWithStatus`` is the fail-open protocol. A plain ``append``
that does not return an ``Event`` raises ``TypeError``.

## 8. Layering violations

| File | Module imported | Why it is suppressed |
|---|---|---|
The explorer violations are fixed: `resolve_failure`, `resolve_roles`, and
`score_diagnosis` now live in `core/diagnosis.py`, with the shared set/pair
metrics in `core/metrics.py`; the explorer and benchmark import them from core.

The sdk violation is fixed: `capture_tool` takes a `provenance_recorder`
callback, so callers pass `core.provenance.record_tool_result_provenance` and
the SDK no longer imports `core`. There are no remaining import-boundary
suppressions.

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

The rows below are cleanup candidates, not boundary code.

| File | Line(s) | Rule |
|---|---|---|
| `adapters/langgraph/mapping.py` | 531 | BLE001 |
| `adapters/langgraph/mapping.py` | 668 | SIM102 |
| `adapters/opencode/mapping.py` | 266 | SIM114 |
| `benchmark/baseline.py` | 220 | SIM105 |
| `benchmark/opencode/runner.py` | 64 | BLE001 |
| `benchmark/opencode/runner.py` | 266 | SIM114 |
| `core/diagnosis.py` | 85 | SIM103 |
| `core/diagnosis.py` | 222, 236, 283, 320, 376, 398, 439 | BLE001 |
| `core/explain.py` | 290, 298, 345, 361 | BLE001 |
| `core/explain.py` | 304 | SIM102 |
| `core/provenance.py` | 211 | SIM114 |
| `core/replay.py` | 70 | SIM118 |
| `sdk/tools.py` | 165 | SIM108 |
| `storage/sqlite.py` | 99, 161 | SIM117 |
| `tests/test_packaging.py` | 63 | SIM300 |
| `tests/test_phase1.py` | 245 | SIM117 |

Cleanup: replace broad catches with the narrow exceptions each helper can
actually raise; let programming errors propagate. Apply the SIM fixes as a
separate mechanical pass.

## 12. Justified boundary catches

These are suppressed because the boundary is intentionally fail-open. Each
suppression now states why it is intentional in code. They still count as
baselines.

| File | Line(s) | Rule / module | Why it is suppressed |
|---|---|---|---|
| `adapters/opencode/server.py` | 29, 56, 81 | BLE001 | Ingest is fail-open by design; telemetry must not break the agent. |
| `explorer/server.py` | 96 | BLE001 | Read-only API converts errors to JSON instead of crashing. |
| `sdk/privacy.py` | 140 | BLE001 | Redaction fallback is intentionally best-effort. |
| `tools/verify/verify.py` | 263, 394 | BLE001 | Verifier reports any failure as evidence instead of crashing. |
| `tests/conftest.py` | 59 | BLE001 | Unreachable PostgreSQL is converted into a test skip. |
| `tests/test_phase2_5.py` | 632 | PGH003 | Monkeypatch helper assigns over an instance method. |

Cleanup: keep the fail-open boundaries documented in code. Tests obtain the
optional driver through `storage._psycopg.load_psycopg_or_skip`, so there are
no direct psycopg imports to baseline.

## 13. Duplicated artifacts

No baseline. Static assets now have `scripts/sync-explorer-static.py --check`
in verify, and the local OpenCode plugin copy has
`scripts/sync-opencode-plugin.py --check`. The plugin check skips when
`.opencode/` is absent (CI), and verifies bytes when installed locally.
