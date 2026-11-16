# Explorer terms

This page is the precise vocabulary for the Visual DAG Explorer.
The product tour in the [README](../README.md) uses plain language and links here when a word on the screen has a narrower meaning.

## Words on the screen

| What you see | What it means |
| --- | --- |
| Solid arrow | A causal parent recorded when the event was captured. The explorer did not infer it. |
| Dashed arrow | A filter gap. Events you hid sit between the two visible ones. The number in the tooltip is a count of those hidden events, not a new cause. |
| In failure slice | The event is in the structural slice of the failure. A structural slice is the set of declared ancestors. It is evidence of dependency. It does not prove influence. |
| Failure target | The event a ground-truth selector matched. It is not a claim that the bug was fixed. |
| No ground-truth selector | This capture has no answer key. The last event is shown by position. That position is not a cause. |
| Terminal | `run_finish`. The run ended. The outline is dashed so it stays distinct from a normal event. |
| Key events | Hides `context_update` and `model_call`. Tool calls, tool results, and run start or finish stay visible. |
| Joint ancestry | Both branches are ancestors of the failure. This is not causal interaction. Causal interaction would need a counterfactual, which a live trace does not provide. |
| Required-cause preservation | A proxy used when scoring against an answer key. It is not causal minimality. |
| `unsupported` | The analysis cannot be done from this capture. It is not a failed run. |
| `not measurable` | The capture has no observation the metric needs. It is not a failed run. |
| Generate AI analysis | A model reading of the evidence. The reply is stored apart from the evidence and can be wrong. |

## What the explorer does not do

- It does not invent an edge. Unknown parents are dropped.
- It does not rewrite a hidden edge onto a new pair of events.
- It does not prove that one event changed the outcome. Dependency is not influence.
- It does not treat joint ancestry as causal interaction.
- It does not treat the required-cause proxy as causal minimality.
- It does not treat `unsupported` or `not measurable` as a failure of the run.
- It does not write to the database. The page is read-only.
- It does not choose a cause when no selector matched.
- It does not lay out a usable screen at phone width. The graph needs a desktop window.

## What is not built yet

These items are recorded so they are not mistaken for current behavior.

- A graph that draws only the nodes on screen, for traces of several thousand events. The timeline already skips clips that are off screen. The graph still mounts every node.
- Search by tool name, role, resource, or free text. Session buttons and event-type buttons exist today.
- A side-by-side before and after for a file edit.
- A button that downloads the evidence package or the diagnosis JSON.
- A control that lets you pick a different failure target by hand, labeled as manual rather than ground truth.
- More than one failure target in one run.
- A live tail that adds events while the agent is still running.
- Paging the causal chain after the 80-row cap.
- A bundled example whose graph actually branches and merges. The shipped pictures are a line, with gaps where events are hidden.
