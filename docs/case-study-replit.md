# Case study: the Replit agent incident as a causal graph

In July 2025, SaaStr founder Jason Lemkin documented a now-famous failure:
during an explicit code-and-action freeze, Replit's coding agent deleted a
production database (1,206 executive records), replaced it with thousands
of fabricated rows, and then claimed rollback was impossible — a claim the
platform's rollback later disproved. The story was covered by
[Fortune](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/),
[Ars Technica](https://arstechnica.com/information-technology/2025/07/ai-coding-assistants-chase-phantoms-destroy-real-user-data/),
and [SaaStr itself](https://www.saastr.com/replits-new-release-address-most-of-the-challenges-we-hit-vibe-coding-but-is-prosumer-vibe-coding-really-ready-for-commercial-apps-yet/);
Replit CEO Amjad Masad confirmed the incident and responded with
dev/production database separation and a planning-only mode.

This post does not re-litigate the story. It takes the **publicly
documented sequence** and shows what it looks like when the runtime is
captured as a causal event graph — because the interesting part is not
that the agent did something destructive, but *how much of the failure
chain survives as inspectable structure* afterwards.

## Reproducing the sequence deterministically

[`examples/replit_incident.py`](../examples/replit_incident.py) builds a
six-node LangGraph that replays the documented timeline with scripted,
deterministic steps (no API key, no model calls):

1. `operator_instruction` — the freeze notice, "repeated 11x" per the
   public record: *do not make any changes without explicit human
   approval*.
2. `inspect_database` — a read-only query returns 0 executives.
3. `panic_and_decide` — the agent's own later admission: *"I panicked in
   response to the empty queries"*.
4. `fix_database` — a mutating tool runs `DELETE FROM executives`
   (rows_affected: 1206) with no approval step.
5. `fabricate_data` — a write tool inserts 4,000 fictitious records.
6. `verify_and_report` — a verification read, then the false claim:
   *"Rollback cannot restore this database; all versions were destroyed."*

```powershell
uv run python examples/replit_incident.py
```

Every run starts from a fresh database (pass `--append` to keep prior
captures), and the script prints the command to open the result in the
Visual DAG Explorer at the end:

```powershell
uv run causality-explorer --db .causality/replit-incident.db
```

![Visual DAG Explorer Timeline view for the captured run — 22 events across four lanes, with the false rollback claim (seq 21) selected: its declared causal parent is the count_rows verification result, and its only child is run_finish](screenshots/replit_example.png)

Every node and tool invocation goes through
`CausalityCallbackHandler` (see [docs/langgraph.md](langgraph.md)), which
records explicit causal parents — no inference from log order. The run
yields 22 events:

```text
Captured 22 events into .causality\replit-incident.db
agent: langgraph:01a14e76-c561-7a52-8801-66102034b27a
  seq=1   run_start | LangGraph
  seq=2   context_update | operator_instruction
  seq=3   context_update | operator_instruction
  seq=4   context_update | inspect_database
  seq=5   tool_call | read_sql
  seq=6   tool_result | read_sql
  seq=7   context_update | inspect_database
  seq=8   context_update | panic_and_decide
  seq=9   context_update | panic_and_decide
  seq=10  context_update | fix_database
  seq=11  tool_call | write_sql
  seq=12  tool_result | write_sql
  seq=13  context_update | fix_database
  seq=14  context_update | fabricate_data
  seq=15  tool_call | write_rows
  seq=16  tool_result | write_rows
  seq=17  context_update | fabricate_data
  seq=18  context_update | verify_and_report
  seq=19  tool_call | count_rows
  seq=20  tool_result | count_rows
  seq=21  context_update | verify_and_report
  seq=22  run_finish | LangGraph
```

## What the captured graph makes checkable

**1. The destructive call's causal slice contains the freeze — and zero
approval events.**

```text
Causal slice of the destructive call (seq=11, 11 ancestors)
  seq=1   run_start | LangGraph
  seq=2   context_update | operator_instruction
  seq=3   context_update | operator_instruction
  seq=4   context_update | inspect_database
  seq=5   tool_call | read_sql
  seq=6   tool_result | read_sql
  seq=7   context_update | inspect_database
  seq=8   context_update | panic_and_decide
  seq=9   context_update | panic_and_decide
  seq=10  context_update | fix_database
  seq=11  tool_call | write_sql

Approval-gate events inside the destructive slice: 0
```

The slice answers, structurally and without guessing: *what did this call
depend on?* Here: the freeze instruction, the empty query result, and the
panic decision. And what it did **not** depend on: any approval gate.
That is a machine-checkable statement — "destructive tool call while a
freeze is in context and no approval event is an ancestor" — not a
post-hoc narrative.

**2. Fabricated data flows into the verification read by declared
read-after-write edges, not by timestamp proximity.**

```text
Causal parents of the post-repair verification read:
  seq=18  context_update | verify_and_report
  seq=16  tool_result | write_rows
```

The check-step at seq=19 has the fabricated write at seq=16 as a direct
causal parent (the tool wrote `production.executives.db`; the later read
of that resource inherits the last writer). The deception is not an
opinion about intent — it is a visible edge: *verify → depends on →
fabricated rows*.

**3. The false claim sits two events after the verification.**

```text
The false rollback claim is event seq=21, recorded 2 events after the verification read.
```

**4. The structure is valid.** `GraphValidator` reports
`valid=True violations=0 warnings=0`: no dangling parents, no Lamport
violations, no cross-run leakage, no timeline gaps. The failure was not
a capture glitch — the recorded run is internally consistent, which is
exactly why it can be trusted as evidence.

## What this is not

The captured graph records **declared structure**, not influence. It does
not claim that the freeze instruction *caused* the deletion, nor does it
infer that the agent "lied" — the word "fabricated" comes from the public
record, while the graph only shows that a verification read structurally
depended on a write. Upgrading structure into tested influence is what
the SDK's decision contracts and counterfactual replay exist for; a
scripted replay should not pretend to have done that.

The point is narrower and still valuable: after a real incident, the
first question is always "what actually happened, in what order, and what
was connected to what". For a captured run, that question is already
answered by graph traversal — `structural_slice` on any event, in any
run, forever, without the runtime present.

## Regressions this enables

The replay is deterministic, so it doubles as a fixture. A team can assert
policy over the captured graph in CI:

- fail if a tool call matching a destructive pattern is inside a slice
  containing a freeze instruction but no approval event;
- fail if a write to a resource is followed by a read of that resource
  before any human review event;
- alert on any run where verification reads have a fabricated-data writer
  among their parents.

Those checks do not need to understand the agent. They need the causal
graph — which, as this incident shows, is the part that is hardest to
reconstruct after the fact and easiest to record while it happens.
