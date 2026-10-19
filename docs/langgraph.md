# LangGraph integration

> Live capture needs **both** libraries: `agent-causality` (PyPI — SDK,
> storage, validation, explorer, CLI) **and** the LangGraph stack
> (`langgraph` + `langchain-core`) that you are already running. The
> adapter is a LangChain callback handler, so it observes whatever the
> runtime dispatches; it never wraps or patches your graph.

Capture a real LangGraph execution:

```text
LangGraph run → callbacks → causal events → slices → grounded diagnosis
```

Adapter: [`adapters/langgraph/mapping.py`](../adapters/langgraph/mapping.py)
(`CausalityCallbackHandler`).
Test: [`tests/test_langgraph_adapter.py`](../tests/test_langgraph_adapter.py).
Worked example of a real failure:
[`docs/case-study-replit.md`](case-study-replit.md) /
[`examples/replit_incident.py`](../examples/replit_incident.py).

## Run it

```powershell
# Source checkout (the dev environment already includes langchain-core/langgraph)
uv sync
uv run python examples/replit_incident.py

# Consumer flow
pip install agent-causality
pip install langgraph langchain-core
```

```python
from adapters.langgraph import CausalityCallbackHandler
from storage.sqlite import SQLiteEventStore

store = SQLiteEventStore(".causality/langgraph.db")
handler = CausalityCallbackHandler(store)

result = app.invoke({"value": 1}, config=handler.config())
# equivalently: app.invoke(inputs, config={"callbacks": [handler]})

# The graph, then the evidence
from core.validator import GraphValidator
from core.slicing import structural_slice

report = GraphValidator(store).validate_run("langgraph")
assert report.is_valid
```

Then inspect the run in the explorer:

```powershell
uv run python -m explorer.server --db .causality/langgraph.db
# (installed equivalent: causality-explorer --db .causality/langgraph.db)
```

## What gets recorded

One root callback (a run whose `parent_run_id` is `None`) becomes one
agent, `langgraph:<root run id>`, with its own Lamport clock. Nested runs
(chain, tool, llm, retriever) become events inside that agent.

| LangChain callback | Event type |
| --- | --- |
| `on_chain_start` (root) | `run_start` |
| `on_chain_start` (nested node) | `context_update` |
| `on_chain_end` (root) | `run_finish` |
| `on_chain_end` (nested node) | `context_update` |
| `on_tool_start` | `tool_call` |
| `on_tool_end` | `tool_result` |
| `on_llm_start` / `on_chat_model_start` | `model_call` |
| `on_llm_end` | `model_call` |
| `on_retriever_start` / `on_retriever_end` | `context_update` |
| any `on_*_error` | `agent_error` (tools: `tool_result` with the error payload) |

Payloads carry the callback phase, run/parent run IDs, resolved run name,
`langgraph_node`/`langgraph_step` metadata when present, and per-kind
inputs/outputs. Tool events also carry `invocation_id` (the LangGraph run
ID), so tool calls and results pair exactly in the reducer.

## Causal edge rules

LangGraph's `parent_run_id` is **containment**, not causality, so the
adapter converts it deliberately:

- **Unknown parent ⇒ dropped.** A callback whose `parent_run_id` was never
  seen (attachment mid-run) is discarded. Causality is never invented.
- **Frontier chaining.** A child's start event parents to the last event
  recorded under its parent run; end/error events parent to the run's own
  last event. After every recorded event, both the run's and its parent's
  frontier advance. Sequential siblings therefore chain in execution order
  over the shared graph state — that order is real, but it is declared as
  sequence, not as influence.
- **Read-after-write.** Tool inputs are scanned for file-path keys
  (`file_path`, `filePath`, `path`, `filename`, `file`). Write-ish tools
  (`write`, `edit`, `create`, `save`, `append`, `patch`, `mkdir`, `touch`)
  register their resource (`file://<path>`); later reads of the same
  resource get the last writer as an extra causal parent. This is how the
  case study shows fabricated data flowing into a verification read.

## Fail-open behavior

Telemetry must never break the agent:

- `raise_error = False`; every callback body is wrapped, and handler
  failures are collected in `handler.errors` instead of raised.
- The store is wrapped with the SDK's fail-open proxy, so an append that
  hits a full disk drops the event and leaves the run untouched
  (covered by `test_capture_survives_store_failure`).
- Duplicate callbacks for the same run are idempotent (deterministic UUID5
  event IDs + idempotency keys), so retries and replayed traces cannot
  double-record.

## Privacy

Payloads pass through the same deep redaction as the OpenCode adapter:
sensitive key/value patterns (API keys, tokens, passwords, bearer strings)
become `[REDACTED]` before storage, and every value is coerced to
JSON-safe primitives with long strings truncated (default 4000 chars).
Redaction is opt-in and best-effort.

## Requirements

- `langchain-core` is optional: without it the handler still imports (a
  stand-in base class is used), so the package never hard-depends on the
  LangChain stack. Install with `pip install agent-causality` plus
  `langchain-core` (extras: `agent-causality[langgraph]`).
- Tested against `langchain-core` 1.6 and `langgraph` 1.2; the
  integration test (`test_real_langgraph_execution_is_captured`) runs a
  real StateGraph and asserts a clean validator report.
