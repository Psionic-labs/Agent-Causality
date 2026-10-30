# Agent-Causality

[![PyPI version](https://img.shields.io/pypi/v/agent-causality)](https://pypi.org/project/agent-causality/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/agent-causality?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=pypi%20downloads)](https://pepy.tech/projects/agent-causality)
[![npm version](https://img.shields.io/npm/v/@psionic-labs/opencode-agent-causality)](https://www.npmjs.com/package/@psionic-labs/opencode-agent-causality)
[![npm downloads](https://img.shields.io/npm/d18m/@psionic-labs/opencode-agent-causality?label=npm%20downloads&labelColor=black&color=green)](https://www.npmjs.com/package/@psionic-labs/opencode-agent-causality)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green)](https://github.com/Psionic-labs/Agent-Causality/blob/main/LICENSE)
[![Website](https://img.shields.io/badge/website-live-orange)](https://psionic-labs.github.io/Agent-Causality/)
[![OpenCode 1.19+](https://img.shields.io/badge/opencode-1.19%2B-purple)](https://opencode.ai)

*Causal debugging for branching multi-agent systems — plus capture adapters for OpenCode and LangGraph.*

Agent-Causality records what your agents did as a causal event graph, then
explains failures with grounded evidence instead of guesses.

> **This README is identical on both registries.** The full system needs
> **both** packages:
>
> - **Python (`agent-causality` on PyPI)** — SDK, CLI, ingest receiver
>   (`causality-opencode-ingest`), and Visual DAG Explorer
>   (`causality-explorer`). Installing only this gives you the offline demo
>   but no live OpenCode capture.
> - **JavaScript (`@psionic-labs/opencode-agent-causality` on npm)** —
>   OpenCode plugin (telemetry capture only). Installing only this gives you
>   events with nowhere to persist or view them.
>
> Source: <https://github.com/Psionic-labs/Agent-Causality>

[Website](https://psionic-labs.github.io/Agent-Causality/) ·
[Demo video](#demo-video) ·
[Install](#install--you-need-both-packages) ·
[30-second demo](#try-it-in-30-seconds-no-server-key-or-network) ·
[Single-run capture](#single-run-capture-ingest--opencode--explorer) ·
[Explorer](#see-it-visual-dag-explorer) ·
[OpenCode](#works-with-opencode) ·
[LangGraph](#works-with-langgraph) ·
[Research paper](#research-paper) ·
[Docs](#documentation)

---

## Demo video

[![Agent-Causality demo — watch on YouTube](https://img.youtube.com/vi/bogmzYe9Hzs/maxresdefault.jpg)](https://www.youtube.com/watch?v=bogmzYe9Hzs)

*Full walkthrough, click the thumbnail to watch on YouTube.*

*The reel also plays in-page on the [website](https://psionic-labs.github.io/Agent-Causality/#demo), alongside the interactive walkthrough.*

*The Video follows the Single-run capture given below*

---

## Why it exists

Logs and traces show *what happened*. When several agents branch, merge, and
share state, that isn't enough to tell *what actually caused* a bad outcome.

Agent-Causality adds three things ordinary observability lacks:

| Gap in ordinary observability | What Agent-Causality records |
| --- | --- |
| Scattered logs, no links | **Explicit causal parents** for every event |
| Decisions with no reference point | **Decision contracts with baselines** |
| Guesses about "what if" | **Counterfactual replay** that tests which inputs flip the outcome |

```text
Agent execution → event capture → causal graph → slice / provenance / interaction → grounded diagnosis
```

---

## Install — you need BOTH packages

Published as `agent-causality==0.3.0`
([PyPI](https://pypi.org/project/agent-causality/)) and
`@psionic-labs/opencode-agent-causality==0.1.7`
([npm](https://www.npmjs.com/package/@psionic-labs/opencode-agent-causality)).
Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
for source checkouts; PyPI/npm consumers only need `pip`/`opencode`.

```bash
# 1. Python side (SDK + receiver + explorer + CLI)
pip install agent-causality
# or, inside a uv project:
uv add agent-causality

# 2. JavaScript side (OpenCode capture plugin — telemetry only)
opencode plugin add @psionic-labs/opencode-agent-causality
```

> **npm-only installers:** you still need the PyPI package — the Visual DAG
> Explorer and the `causality-opencode-ingest` receiver ship **only** in
> `agent-causality`, not in this npm package.
>
> **PyPI-only installers:** you still need the npm package for live OpenCode
> capture — `pip install agent-causality` alone cannot observe an OpenCode
> session without the plugin.

*Optional — AI explanation extra.* Only needed for LLM-grounded `explain` /
*Generate AI analysis* (needs `httpx` + `OPENROUTER_API_KEY`):

```bash
# pip consumer
pip install "agent-causality[explain]"
# uv project
uv add "agent-causality[explain]"
# source checkout
uv sync --extra explain
```

---

## Try it in 30 seconds (no server, key, or network)

```bash
uv run python examples/customer_approval.py
```

It captures two agent results and a wrong approval, then explains the failure:

```text
Outcome: approved
Diagnosis: The terminal event is marked 'failure' because the decision returned
'approved' with customer_status='eligible' and risk_score=0.2.
Evidence:
- Minimal tested chain: customer_status + risk_score -> decision -> terminal failure
- Canonical baselines were 'ineligible' and 0.8
- Interaction between customer_status and risk_score: 1.0
Limitations: the evidence does not establish why the upstream tools produced these values.
```

---

## Single-run capture: ingest → opencode → explorer

The minimal end-to-end loop. One isolated SQLite file per run keeps traces
separate (`.causality/single-run.db` below is just an example — any path
works) and port `8797` avoids clashing with the default `8766` explorer.

**Terminal 1 — start the receiver:**

```bash
# PyPI install
causality-opencode-ingest --db .causality/single-run.db
# Source checkout
uv run causality-opencode-ingest --db .causality/single-run.db
```

**Terminal 2 — run one instrumented agent task** (plugin posts automatically):

```bash
opencode run "Run the existing tests before editing. Diagnose and fix the bug in discount.py so both tests pass. Do not modify the tests. Rerun the tests and summarize the change."
```

*Optional — enable AI explanations for this project:*

```bash
uv add "agent-causality[explain]"
# pip equivalent: pip install "agent-causality[explain]"
```

**Terminal 3 — inspect the trace in the Visual DAG Explorer:**

```bash
# PyPI install
causality-explorer --db .causality/single-run.db --port 8797
# Source checkout
uv run python -m explorer.server --db .causality/single-run.db --port 8797
```

Then open <http://127.0.0.1:8797>. Each `opencode run` appends to the same
`--db` file; use a fresh `--db` path per task for one-trace-per-file
(any filename works).

---

## See it: Visual DAG Explorer

Open any capture as an interactive causal graph — no API key needed.
The Explorer ships inside the `agent-causality` PyPI wheel (no clone needed):

```bash
# PyPI install
pip install agent-causality
causality-explorer
causality-explorer --db .causality/opencode.db --port 8766
```

```bash
# Source checkout
uv run python -m explorer.server
uv run python -m explorer.server --db .causality/opencode.db --port 8766
# Single-run variant from the section above:
uv run python -m explorer.server --db .causality/single-run.db --port 8797
```

Then open <http://127.0.0.1:8766> (or `:8797` for the single-run variant).
The bundled demo trace loads: a failing test, the fix edit, and the passing
retry, with the failure path highlighted.

![Animated tour of the Visual DAG Explorer — graph, timeline, and metrics views](https://github.com/Psionic-labs/Agent-Causality/raw/main/docs/media/explorer-demo.gif)

*Short tour of the bundled demo trace: select the failing `tool_result`,
switch to the Timeline view, open the Metrics census, then return to the
graph. Also available as [MP4](https://github.com/Psionic-labs/Agent-Causality/raw/main/docs/media/explorer-demo.mp4).*

![Visual DAG Explorer — live OpenCode trace with the failure target selected, causal edges, and inspector](https://github.com/Psionic-labs/Agent-Causality/raw/main/docs/screenshots/explorer-shared-state-fresh.png)

*Freshly captured `shared_state_contamination` run (240 events, 6 causal
edges) — the checker's failing `tool_result` selected. The header reads
**Fallback target** because the diagnosis target came from the last-event
fallback; its command and result are in the inspector.*

![Visual DAG Explorer Timeline view — per-agent lanes in sequence order, the failure target selected, with minimap and event inspector](https://github.com/Psionic-labs/Agent-Causality/raw/main/docs/screenshots/timeline.png)

*Bundled demo trace in the Timeline view — per-agent lanes (run, bash, edit),
the retry's `tool_result` ("app tests pass") selected as the failure target,
with the "Why did it fail?" strip and event inspector alongside. The chrome
is cosmetic; the top strip reads **Read-only** because the explorer never
writes to a capture.*

What you get:

- **Graph + Timeline views** of the declared causal parents — every edge
  was recorded at capture time, none inferred.
- **Event inspector** — click any node for its command, result, parents,
  and children.
- **Analysis tabs** (chain, provenance, interaction, evidence, metrics)
  stay informative even with no ground truth, built from capture facts.
- **Your own runs**: point it at a live capture —
  `causality-explorer --db .causality/opencode.db`
  (source checkout: `uv run python -m explorer.server --db .causality/opencode.db`).
- **Optional AI interpretation**: install the `explain` extra
  (`pip install "agent-causality[explain]"` / `uv add "agent-causality[explain]"`),
  set `OPENROUTER_API_KEY` (and optionally `OPENROUTER_MODEL`, default
  `nvidia/nemotron-3-ultra-550b-a55b:free`), then click *Generate AI analysis*
  in the "Why did it fail?" strip. The model text lives in its own labeled
  block — never mixed with the evidence.

Full acceptance procedure:
[TEST.md §29](https://github.com/Psionic-labs/Agent-Causality/blob/main/TEST.md).

---

## Use it with your agents

```python
import causality

causality.init(".causality/events.db")

@causality.agent(role="risk_checker")
def check_risk(customer): ...

@causality.merge_decision(...)
def approve(customer_status, risk_score): ...
```

See
[`examples/customer_approval.py`](https://github.com/Psionic-labs/Agent-Causality/blob/main/examples/customer_approval.py)
for a complete runnable example.

---

## Works with OpenCode

Capture live coding-agent sessions. Telemetry is fail-open: it never
interrupts your agent. **Requires both packages** (receiver from PyPI,
plugin from npm).

```bash
# Terminal 1: receiver (PyPI install; source checkout: uv run causality-opencode-ingest ...)
causality-opencode-ingest --db .causality/opencode.db
# Terminal 2: agent (plugin posts automatically)
opencode run "Read RESEARCH.md, implement sort_items in task.py as recommended, run the test script."
# Terminal 3: Visual DAG
causality-explorer --db .causality/opencode.db
```

Full consumer flow: install `agent-causality` (PyPI) → install the OpenCode
plugin (`opencode plugin add @psionic-labs/opencode-agent-causality`, npm) →
start the receiver → run OpenCode → launch `causality-explorer` → inspect the
recorded trace. No repository clone is needed.

> Representative committed result (`stale_research`, OpenCode `1.19.0`):
> `completed (exit 0), 331 events, capture coverage 1.0, diagnosis scored`
> (see `benchmark/results/opencode/opencode.md`). No video artifact ships
> with this release.
> [Setup guide →](https://psionic-labs.github.io/Agent-Causality/opencode.html)

### What the plugin captures

The npm plugin forwards OpenCode's global event stream plus explicit hooks
(`tool.execute.before/after`, `permission.ask`, `command.execute.before`,
`chat.message`, `chat.params`). The Python receiver maps these onto canonical
events, registers file writes with Resource-Version machinery, and redacts
secrets before SQLite persistence. It is telemetry capture only — the
Explorer and CLI live in the PyPI distribution.

---

## Works with LangGraph

`CausalityCallbackHandler` is a LangChain callback handler: point your
graph's `config` at it and every node, tool, and LLM run lands in the
causal graph — fail-open, with `parent_run_id` containment converted into
explicit causal edges (unknown parents are dropped, never invented).

```python
from adapters.langgraph import CausalityCallbackHandler
from storage.sqlite import SQLiteEventStore

store = SQLiteEventStore(".causality/langgraph.db")
handler = CausalityCallbackHandler(store)

app.invoke(inputs, config=handler.config())
```

Worked example: a deterministic replay of the documented July 2025 Replit
incident — freeze violated, production rows deleted, fabricated data
written, false rollback claim — captured as 22 causally-validated events
in
[`examples/replit_incident.py`](https://github.com/Psionic-labs/Agent-Causality/blob/main/examples/replit_incident.py)
(write-up:
[the Replit case study](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/case-study-replit.md)).
[Adapter guide →](https://psionic-labs.github.io/Agent-Causality/langgraph.html)

---

## Benchmarks

Offline, provider-neutral suite (`uv run causality-benchmark ...`) plus a
real OpenCode coding-agent benchmark. Full results in
[`docs/benchmarks.md`](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/benchmarks.md)
and `benchmark/results/`.

- Five deterministic scenarios: **5/5 pass**.
- Experiment 2 (shared-state recovery): **100/100**.
- Experiment 3 (semantic-port vs raw deletion): **20/20** semantic-port
  successes; raw-deletion failure rate met target.
- Experiment 1 (offline): passes; external Fastino run is
  provider-blocked/deferred (no structured-output capability).
- Real OpenCode benchmark (5 runs / 5 tasks, OpenCode `1.19.0`): capture
  micro/macro-average `1.0`; cause recall mean `0.3` (structural-slice
  ancestry under explicit-evidence edges only); joint ancestry `0.0` —
  genuine causal interaction is unsupported from live traces.

*Terminology is precise: live-trace branch results are reported as
`joint ancestry` (not causal interaction), and minimal slices as a
`required-cause preservation proxy` (not causal minimality).*

---

## Research paper

[Agent-Causality: Declared Dependency Tracing and Counterfactual Sensitivity Analysis for Multi-Agent Systems](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf), by Vasant Kumar Mogia, Psionics. The file is [`research_paper/agentic_causality_paper.pdf`](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf). Source is [`research_paper/main.tex`](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/main.tex).

The paper describes declared parent links, structural slices, provenance grades, decision contracts, and counterfactual replay of registered merge decisions.

Each name links to the PDF page where that section starts.

1. [Introduction](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=1)
2. [The problem](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=2)
3. [The core idea](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=2)
4. [How the system works](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=3)
5. [Fixture walkthrough: customer approval](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=5)
6. [What the tool supports on its own](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=6)
7. [Combinations with other tools](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=6)
8. [Case study: a documented agent incident](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=8)
9. [Evaluation](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=8)
10. [Limitations and future work](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=10)
11. [Related work](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=11)
12. [Conclusion](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf#page=11)

---

## Documentation

| Topic | Link |
| --- | --- |
| Getting started | [GETTING_STARTED.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/GETTING_STARTED.md) |
| OpenCode integration | [OpenCode guide](https://psionic-labs.github.io/Agent-Causality/opencode.html) |
| LangGraph integration | [LangGraph guide](https://psionic-labs.github.io/Agent-Causality/langgraph.html) |
| Replit incident case study | [docs/case-study-replit.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/case-study-replit.md) |
| CLI and Python reference | [docs/reference.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/reference.md) |
| Benchmarks and results | [docs/benchmarks.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/benchmarks.md) |
| Scope and limits | [docs/reference.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/reference.md) |
| Research paper | [`research_paper/agentic_causality_paper.pdf`](https://github.com/Psionic-labs/Agent-Causality/blob/main/research_paper/agentic_causality_paper.pdf) |
| Research background | [docs/thesis.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/thesis.md), [docs/research-memo.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/docs/research-memo.md) |
| Contributing and tests | [TEST.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/TEST.md), [CONTRIBUTING.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/CONTRIBUTING.md) |
| Release notes | [CHANGELOG.md](https://github.com/Psionic-labs/Agent-Causality/blob/main/CHANGELOG.md) |
