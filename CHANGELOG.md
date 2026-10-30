# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-10-30

### Breaking changes

- `capture_tool` now requires `provenance_recorder` when `field_sources`
  produces a non-empty mapping. Callable recorders must return an `EventLog`,
  and captured tool retries without provenance are rejected.

### Failure story on the causal DAG

- The failure column now shows the failure's visible declared ancestors, not
  only the immediate slice. Hidden stretches become dashed filter gaps or
  stubs with the omitted event count, and selecting a node lights only its
  causal ancestors, stopping at a gap.
- Gap tooltips report their hidden count, and the count survives when the same
  visible pair also has a direct causal edge.
- Zoom and pan map pointer movement through the SVG letterbox, so anchors stay
  under the cursor at every viewport aspect ratio.
- The explorer opens the session that owns the failure event by default; an
  explicit session choice still wins.

### Capture, CLI, and explorer boundaries

- Replay intervention values that are neither JSON nor a bare identifier now
  fail with usage guidance instead of silently becoming a string.
- `EventLog.append` must return the stored `Event` or raise. Fail-open logs
  implement `append_with_status` through the new `AppendWithStatus` protocol,
  and malformed append returns raise `TypeError`.
- The explorer serves only the vendored `explorer/static` bundle; the
  `frontend/out` fallback is gone.
- `.env` loading moved to `sdk/env.py`. Inline comments are stripped from
  unquoted values, and unreadable files fail at startup.
- Diagnosis scoring moved from the OpenCode benchmark into `core/diagnosis.py`
  and `core/metrics.py`, ready for non-benchmark callers.

### Examples, site, and docs

- New payment approval failure example (`examples/payment_approval.py`) with
  CLI coverage.
- The site was redesigned as a causal-graph landing page, with OpenCode and
  LangGraph guides and a mobile menu.
- The research paper is published with Google Scholar metadata, and the README
  shows live PyPI and npm download badges.

### Verification and agent tooling

- `tools/verify/verify.py` now provides deterministic quick and full modes,
  ephemeral ports, PASS/FAIL timings, and per-run artifact logs; pre-commit,
  CI, and the agent workflow run it.
- New checks enforce import boundaries, suppression budgets from `CLEANUP.md`,
  static-bundle freshness, the installed plugin copy, and linked-worktree
  hygiene.
- Added the parallel worktree spawner (capped at three agents), the worktree
  cleanup command, task-scope enforcement for spawned branches, and an advisory
  pull request review job.
- The failure-story, viewport, and default-session regressions are covered by
  node tests, and the explorer Playwright smoke test remains the browser gate.

### npm plugin 0.1.7

- `@psionic-labs/opencode-agent-causality` 0.1.7 republishes the README with
  the synced website, paper, guide, and download-badge links. Plugin runtime
  behavior is unchanged from 0.1.6.

## [0.2.1] - 2026-10-22

### Visual DAG Explorer — CRT monitor skin

- The explorer now wears the marketing site's CRT causal-monitor system: a
  beige chassis with red control strips, a crimson screen with vignette and
  glare, HUD-style amber labels, and scanlines confined to the graph/timeline
  surfaces. The top strip reads **Read-only**, not REC.
- IBM Plex Mono 400/500/600 ships locally as woff2 (SIL OFL); the explorer
  makes no external font requests. DAG events render as 18px squares, and the
  Timeline uses the same warm palette (gold slice, deep-red failure, dashed
  teal terminal, amber selection).
- README media refreshed: four regenerated stills plus
  `docs/media/explorer-demo.gif` and `.mp4`, produced by the new
  zero-dependency `scripts/capture-explorer-media.mjs` (Edge/Chrome CDP +
  ffmpeg). `docs/opencode.md` documents the capture flow.
- No backend, endpoint, selection, status-language, or §8 terminology changes;
  the read-only contract is unchanged.
- npm `@psionic-labs/opencode-agent-causality` 0.1.6 republishes the
  README with the new visual tour; plugin runtime code is unchanged.

## [0.2.0] - 2026-10-18

### Capture adapters package + LangGraph integration

- **Breaking (pre-1.0):** direct imports of `opencode_adapter` must move to
  `adapters.opencode`; the `causality-opencode-ingest` entry point is
  unchanged.
- New `adapters/` package: the OpenCode runtime capture moved from
  `opencode_adapter/` to `adapters/opencode/` (history preserved; the
  `causality-opencode-ingest` entry point now targets
  `adapters.opencode.server:main`).
- New LangGraph adapter: `CausalityCallbackHandler`
  (`adapters/langgraph/mapping.py`) records every chain/tool/LLM/retriever
  callback as causal events — one root run becomes one agent, unknown
  parents are dropped, frontier chaining orders siblings, resource
  read-after-write edges link file readers to last writers, event IDs are
  deterministic and idempotent, payloads are deeply redacted and coerced
  JSON-safe, and capture is fail-open (`handler.errors`, never raises into
  the agent). `langchain-core` stays optional; extras:
  `agent-causality[langgraph]`.
- Shared deep-redaction helper (`adapters/redaction.py`); the sensitive-key
  regex was tightened so keys like `token_usage` are no longer redacted
  while `access_token`-style keys still are.
- Deterministic case study: `examples/replit_incident.py` replays the
  documented July 2025 Replit incident as a captured causal graph
  (write-up: `docs/case-study-replit.md`). Runs start from a fresh database
  by default (`--append` keeps prior captures) and print the exact
  `causality-explorer` command for the result.
- Visual DAG Explorer: node labels now fall back to the generic callback
  `name` field, so LangGraph runs render meaningful labels
  (`tool_call · write_sql`) instead of repeating the event type; the DAG,
  failure, diagnosis, and evidence endpoints all work on LangGraph captures.
- Docs: new `docs/langgraph.md`; README gains a LangGraph section and
  documentation-table rows (PyPI and npm copies re-synced byte-identical,
  also picking up the previously missing demo-video section).
- The root `.opencode/` directory (an installed copy of the canonical
  plugin at `packages/opencode-agent-causality/src/index.ts`) is now
  git-ignored and no longer tracked; the plugin-compat script installs the
  canonical source into `<workdir>/.opencode/plugins/` before running.

## [0.1.4] - 2026-10-14

### Unified README for both registries (docs only)

- Root `README.md` (PyPI long description) and
  `packages/opencode-agent-causality/README.md` (npm) are now byte-identical:
  badges, quick-nav, both-packages install callout, single-run
  ingest → opencode → explorer loop (example `.causality/single-run.db`
  placeholder, any path works; `--port 8797`), `explain` extra install for
  `pip` and `uv`, and absolute GitHub links so both registries render.
- `GETTING_STARTED.md`, `docs/opencode.md`, and `docs/reference.md` carry
  the same single-run commands and cross-install notes (npm needs the PyPI
  receiver/explorer; PyPI needs the npm plugin for live capture).
- No code changes since 0.1.3.

## [0.1.3] - 2026-10-13

### Visual DAG Explorer ships in the PyPI wheel (packaging fix)

- The `agent-causality` wheel now bundles the compiled Visual DAG frontend
  (`explorer/static/`, 20 files: `index.html` + `_next/` JS/CSS), vendored
  from `frontend/out/` via `scripts/sync-explorer-static.py`. Previously the
  wheel/sdist contained only `explorer/*.py` + demo JSONs, so
  `python -m explorer.server` from a PyPI install 404'd on `/` (the
  `frontend/out/` directory is gitignored and was never packaged).
- `explorer.server.get_frontend_dir()` resolves `explorer/static/` inside the
  installed package without relying on CWD or the checkout layout (legacy
  `frontend/out/` fallback kept for development).
- New `causality-explorer` console entry point (`explorer.server:main`),
  alongside the existing `causality-opencode-ingest` receiver. Consumer flow
  with no clone: `pip install agent-causality` → install the OpenCode plugin
  → `causality-opencode-ingest --db .causality/opencode.db` → run OpenCode →
  `causality-explorer --db .causality/opencode.db`.
- `MANIFEST.in` + `package-data` (`explorer: demo/*.json, static/*,
  static/**/*`) guarantee wheel + sdist coverage; `tests/test_packaging.py`
  fails if the frontend bundle, the asset references, the entry points, or
  the CWD-independent resolution regress.

### OpenCode plugin telemetry 

- Batched delivery: envelopes drain in batches of up to
  `CAUSALITY_OPENCODE_BATCH_MAX` (default 25) per POST; singletons stay
  single objects. Short `persisted`/`accepted` counts retry the batch;
  count-less 2xx bodies still count as delivered.
- Quiet fail-open by default: delivery warnings emit only when
  `CAUSALITY_OPENCODE_LOG_TELEMETRY_FAILURES=1`/`true`, rate-limited, with
  the first warning naming the endpoint and receiver start command.
- Per-request config: endpoint, bearer token, timeout
  (`CAUSALITY_OPENCODE_INGEST_TIMEOUT_MS`, default 5000), and batch size
  resolve per request; retry backoff is 200ms/400ms.
- CI frontend job now uses Node.js 24.

### Docs: refreshed to match current behavior

- All user-facing docs synced to the working tree: GETTING_STARTED
  (OpenCode 1.19.0, explorer coverage, current AI model default),
  `docs/reference.md` (explorer/ingest endpoints, plugin env table,
  benchmark commands), `docs/opencode.md` and the npm README (quiet
  fail-open default, batching/backoff, full env table),
  `docs/benchmarks.md` and `benchmark/README.md` (retired-model notes),
  README (AI default), CONTRIBUTING (frontend gates), PROOF.md,
  LEGACY_README.md, and `frontend/DESIGN.md` (current suite counts).

### Docs: TEST.md slimmed, verification archive

- `TEST.md` shrank from ~1100 to ~340 lines: it now covers the quick
  gates, benchmark verification, a fixture CLI smoke block, a
  focused-test-files table, short PostgreSQL notes, and the current
  Phase 5/6, OpenCode (§28), and explorer (§29) procedures. Section
  numbers 28/29 are unchanged, so existing links still resolve.
- The historical Phase 2-4 PostgreSQL/SQL checks (§§1-24) moved
  verbatim to `docs/verification-archive.md` with a status banner;
  `GETTING_STARTED.md` now links there for schema/query detail.

## [0.1.2] - 2026-10-11

### AI diagnosis model default and error mapping (Python distribution)

- `DEFAULT_MODEL` is now `nvidia/nemotron-3-ultra-550b-a55b:free`:
  `deepseek/deepseek-v4-flash:free` was retired from OpenRouter's free
  tier (HTTP 404, "unavailable for free"), which broke the explorer's
  opt-in *Generate AI analysis* (`/api/ai-diagnosis` → 502) and the
  `explain` CLI default. Override per call with `OPENROUTER_MODEL`.
- `/api/ai-diagnosis` no longer leaks model-layer failures as HTTP 500:
  `ImportError` (e.g. missing `httpx`) maps to 503 `ai_unavailable` and
  any other unexpected model error maps to 502 `ai_error` with the
  cause attached. The frontend now surfaces the backend's error body
  instead of a bare status code.

## [0.1.1] - 2026-10-11

### OpenCode plugin loader compatibility

- The plugin default export is now the V1 server-plugin module
  (`{ id: "agent-causality", server: AgentCausalityPlugin }`), supported
  since OpenCode `1.18.29`. Previously the bare-function default export
  fell through to the legacy loader, where the `telemetryStats` object
  export silently disabled the whole plugin on OpenCode `>= 1.19`
  (`Plugin export is not a function`, 0 events ingested).
- Regression coverage: `test/loader-compat.test.mjs` pins the V1 contract
  in `npm test`; `scripts/check-opencode-plugin-compat.py` verifies actual
  loading on real binaries (verified: `1.19.0` with 83 events, `1.18.34`
  with 86 events, 0 receiver errors).

### Real OpenCode benchmark (fresh rerun, 2026-10-11)

- `uv run causality-benchmark opencode --model
  openrouter/deepseek/deepseek-v4-flash`: 5 runs / 5 tasks on OpenCode
  `1.19.0`, all completed, 0 deviations; artifacts committed under
  `benchmark/results/opencode/`.
- Capture micro/macro-average `1.0`; cause recall mean `0.3`
  (structural-slice ancestry under explicit-evidence edges only); joint
  ancestry `0.0` (genuine causal interaction unsupported from live
  traces); provenance `1.0`; distractors `1.0`.
- This replaces the earlier 7-run result (capture `0.928`/`0.967`, cause
  `1.0`), which was scored from stale traces with linear chaining and
  must not be reused.

### Visual DAG Explorer (core feature, Python distribution)

- The explorer (`uv run python -m explorer.server`, serves its own
  bundled frontend) is part of this release: graph + timeline over
  recorded causal edges, event inspector, and analysis tabs that stay
  informative with no ground truth.
- README showcases a screenshot captured from a fresh
  `shared_state_contamination` trace (240 events, 6 causal edges,
  `docs/screenshots/explorer-shared-state-fresh.png`); the reproducible
  capture → serve → view flow is documented in `docs/opencode.md`.
- Scope note: `@psionic-labs/opencode-agent-causality@0.1.1` is the
  telemetry-capture plugin only (hooks, buffering, fail-open delivery) —
  installing it does not install the visual interface, which ships with
  the `agent-causality` Python distribution.

## [0.1.0] - 2026-10-06

First public release. Published to PyPI as `agent-causality==0.1.0`.

### Causal graph / capture

- Event capture for tool, memory, model, and lifecycle events with logical
  sequences and explicit causal parents (`sdk`, `core`).
- SQLite, in-memory, and PostgreSQL event stores plus a graph validator
  (dangling parents, cross-run edges, sequence progression, decision-port
  reachability).
- Deterministic state reconstruction at a logical sequence.

### Replay

- Merge-local counterfactual replay via registered decision evaluators.
- Replay does not re-execute downstream side effects.

### Structural / minimal causal analysis

- Structural slices over declared dependencies.
- Delta-debugging reduction to a tested minimal subset (reported as a
  required-cause preservation proxy, not causal minimality).

### Provenance

- Exact provenance over recorded deterministic field paths; unverified neural
  boundaries stay coarse. Redaction is opt-in and best-effort.

### Interaction analysis

- Shapley values and interaction indices over decision ports (up to four
  ports exact enumeration). Bootstrap sign proportions are descriptive, not
  p-values. Live-trace joint-branch ancestry is reported as joint ancestry,
  not causal interaction.

### Benchmark suite

- Offline, provider-neutral suite calling the same capture/graph/replay
  APIs as the application (`uv run causality-benchmark ...`):
  - five deterministic scenarios (`single_cause`, `multiple_parents`,
    `interaction`, `distractor`, `memory_contamination`): 5/5 pass;
  - Experiment 2 (shared-state dependency recovery): 100/100;
  - Experiment 3 (semantic-port vs raw-text deletion): 20/20 semantic-port
    successes, raw-deletion failure rate 0.7 (target > 0.35 met);
  - failure-injection controls: 3/3 pass.
- Experiment 1 (offline): deterministic 2x2 counterfactual evaluation passes
  (12 true positives / 12 true negatives for both Agent-Causality Shapley and
  the naive 2x2 contrast).
- Experiment 1 (external, Fastino): explicitly provider-blocked and deferred.
  The current Fastino catalog exposes no structured-output capability and
  `fastino/GLiNER-2.5-Decide` returns a single `intent` classification rather
  than independent `good`/`bad` branch decisions, so no external Experiment 1
  was completed.

### `agent-replay` baseline

- `uv run causality-benchmark baseline` runs real `ingest` / `list` / `diff`
  with `clay-good/agent-replay 0.2.0` (commit
  `ccda6229a9451692fb6f1d6d323dd825c2be9dbb`) against all five scenarios.
- Scored as divergence localization only; multi-parent causality,
  interactions, shared-state causality, distractor reasoning, and minimal
  reduction are explicitly unsupported by the baseline.

### OpenCode adapter

- Fail-open OpenCode V1 plugin at `.opencode/plugins/agent-causality.ts`
  (global `event` hook plus `tool.execute.before/after`, `permission.ask`,
  `command.execute.before`, `chat.message`, `chat.params`; 256-envelope
  buffer, 3 retries, telemetry never interrupts OpenCode).
- Local ingest receiver `causality-opencode-ingest`
  (`POST /v1/opencode/events`, optional bearer token, privacy redaction
  before SQLite storage).

### Real OpenCode benchmark

- `uv run causality-benchmark opencode` runs real OpenCode coding-agent
  sessions (`1.18.34`) with the plugin enabled, then scores minimum expected
  event-class coverage and diagnosis quality.
- Committed result: capture micro-average `0.928`, macro-average `0.967`
  across 7 runs / 5 tasks; non-deviated cause identification `1.0` (4 runs);
  3 `shared_state_contamination` runs are agent deviations (the agent refused
  the unsafe override), not adapter failures.
- Live-trace minimal slices are a required-cause preservation proxy
  (causal minimality not measurable); live-trace branch results are joint
  ancestry (causal interaction unsupported).

### Availability

- Python: install with `uv add agent-causality` or `uv pip install agent-causality`
  (`agent-causality==0.1.0` on PyPI).
- OpenCode plugin: `opencode plugin add @psionic-labs/opencode-agent-causality`
  (`@psionic-labs/opencode-agent-causality==0.1.0` on npm).
- Ground-truth JSONs ship inside the distribution (`benchmark/ground_truth`,
  `benchmark/opencode/ground_truth`).
