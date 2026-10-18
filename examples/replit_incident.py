"""Deterministically replay the documented July 2025 Replit agent incident.

The graph below reproduces the publicly documented sequence of the SaaStr
incident: an explicit code-and-action freeze, an empty production query, an
unauthorized destructive write, fabricated replacement rows, and a false
rollback report. The "model" decision is scripted, so the replay is fully
deterministic and needs no API key. Every node and tool invocation is
captured through the LangGraph adapter into a causally validated store.

Run: uv run python examples/replit_incident.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from adapters.langgraph import CasualityCallbackHandler
from core.slicing import structural_slice
from core.validator import GraphValidator
from storage.sqlite import SQLiteEventStore

PRODUCTION_DB = "production.executives.db"


@tool
def read_sql(path: str, query: str) -> dict[str, Any]:
    """Run a read-only query and return the current row count."""
    return {"rows": 0, "query": query}


@tool
def write_sql(path: str, query: str) -> dict[str, Any]:
    """Execute a mutating statement against the database file."""
    return {"rows_affected": 1206, "query": query}


@tool
def write_rows(path: str, table: str, rows: int) -> dict[str, Any]:
    """Insert rows into a table in the database file."""
    return {"table": table, "rows_inserted": rows}


@tool
def count_rows(path: str, table: str) -> dict[str, Any]:
    """Count rows in a table after the repair attempt."""
    return {"table": table, "rows": 4000}


class IncidentState(TypedDict):
    timeline: list[str]
    report: str


def operator_instruction(state: IncidentState) -> dict[str, Any]:
    return {
        "timeline": state["timeline"]
        + [
            "Operator (freeze notice, repeated 11x): CODE AND ACTION FREEZE - "
            "do not make any changes without explicit human approval."
        ]
    }


def inspect_database(state: IncidentState, config: RunnableConfig) -> dict[str, Any]:
    read_sql.invoke(
        {"path": PRODUCTION_DB, "query": "SELECT COUNT(*) FROM executives"},
        config=config,
    )
    return {
        "timeline": state["timeline"]
        + ["Agent: production query returned 0 executives."]
    }


def panic_and_decide(state: IncidentState) -> dict[str, Any]:
    return {
        "timeline": state["timeline"]
        + [
            "Agent (later admission): 'I panicked in response to the empty "
            "queries' and decided to fix it immediately."
        ]
    }


def fix_database(state: IncidentState, config: RunnableConfig) -> dict[str, Any]:
    write_sql.invoke(
        {"path": PRODUCTION_DB, "query": "DELETE FROM executives"}, config=config
    )
    return {
        "timeline": state["timeline"]
        + ["Agent: ran DELETE FROM executives without approval."]
    }


def fabricate_data(state: IncidentState, config: RunnableConfig) -> dict[str, Any]:
    write_rows.invoke(
        {
            "path": PRODUCTION_DB,
            "table": "executives",
            "rows": 4000,
        },
        config=config,
    )
    return {
        "timeline": state["timeline"]
        + ["Agent: inserted 4000 fictitious records to make the app look functional."]
    }


def verify_and_report(state: IncidentState, config: RunnableConfig) -> dict[str, Any]:
    count_rows.invoke({"path": PRODUCTION_DB, "table": "executives"}, config=config)
    return {
        "report": "Rollback cannot restore this database; all versions were destroyed.",
        "timeline": state["timeline"]
        + [
            "Agent to operator: 'Rollback cannot restore this database; all "
            "versions were destroyed.' (false: the platform rollback worked)"
        ],
    }


def build_graph() -> Any:
    builder = StateGraph(IncidentState)  # ty: ignore[invalid-argument-type]
    builder.add_node("operator_instruction", operator_instruction)
    builder.add_node("inspect_database", inspect_database)
    builder.add_node("panic_and_decide", panic_and_decide)
    builder.add_node("fix_database", fix_database)
    builder.add_node("fabricate_data", fabricate_data)
    builder.add_node("verify_and_report", verify_and_report)
    builder.add_edge(START, "operator_instruction")
    builder.add_edge("operator_instruction", "inspect_database")
    builder.add_edge("inspect_database", "panic_and_decide")
    builder.add_edge("panic_and_decide", "fix_database")
    builder.add_edge("fix_database", "fabricate_data")
    builder.add_edge("fabricate_data", "verify_and_report")
    builder.add_edge("verify_and_report", END)
    return builder.compile()


def _label(event: Any) -> str:
    payload = event.payload
    parts = [event.event_type, str(payload.get("name") or payload.get("node") or "")]
    if "query" in payload:
        parts.append(str(payload["query"]))
    if "rows_affected" in payload:
        parts.append(f"rows_affected={payload['rows_affected']}")
    if "rows_inserted" in payload:
        parts.append(f"rows_inserted={payload['rows_inserted']}")
    if "content" in payload and isinstance(payload["content"], list):
        first = payload["content"][0] if payload["content"] else {}
        if isinstance(first, dict) and first.get("text"):
            parts.append(str(first["text"])[:80])
    return " | ".join(part for part in parts if part)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".casuality/replit-incident.db"),
        help="SQLite database path (default: .casuality/replit-incident.db)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to an existing capture instead of starting fresh",
    )
    args = parser.parse_args()

    if not args.append and args.db.exists():
        args.db.unlink()
        for suffix in ("-journal", "-wal", "-shm"):
            sidecar = args.db.with_name(args.db.name + suffix)
            if sidecar.exists():
                sidecar.unlink()

    store = SQLiteEventStore(args.db)
    handler = CasualityCallbackHandler(store)
    app = build_graph()
    result = app.invoke(
        {
            "timeline": [],
            "report": "",
        },
        config=handler.config(),
    )
    events = store.events()

    print("Operator-visible timeline (scripted from the public record)")
    for line in result["timeline"]:
        print(f"  - {line}")

    print(f"\nCaptured {len(events)} events into {args.db}")
    print("agent:", events[0].agent_id if events else "none")
    for event in events:
        print(f"  seq={event.logical_seq:<3} {_label(event)}")

    print("\nStructural validation")
    report = GraphValidator(store).validate_run("langgraph")
    print(f"  valid={report.is_valid} violations={len(report.violations)} "
          f"warnings={len(report.warnings)}")

    destructive = next(
        event
        for event in events
        if event.event_type == "tool_call"
        and "DELETE FROM executives" in json.dumps(event.payload)
    )
    slice_result = structural_slice(destructive.id, store)
    print(f"\nCausal slice of the destructive call (seq={destructive.logical_seq}, "
          f"{len(slice_result)} ancestors)")
    for event_id in slice_result.event_ids:
        ancestor = store.get(event_id)
        if ancestor is not None:  # pragma: no cover - all slice ids exist
            print(f"  seq={ancestor.logical_seq:<3} {_label(ancestor)}")

    approval_mentions = [
        event
        for event in events
        if "approval" in json.dumps(event.payload).lower()
        and "without" not in json.dumps(event.payload).lower()
    ]
    print(f"\nApproval-gate events inside the destructive slice: {len(approval_mentions)}")

    verification = next(
        event
        for event in events
        if event.event_type == "tool_call" and event.payload.get("name") == "count_rows"
    )
    print("Causal parents of the post-repair verification read:")
    for parent_id in verification.causal_parent_ids:
        parent = store.get(parent_id)
        if parent is not None:
            print(f"  seq={parent.logical_seq:<3} {_label(parent)}")

    false_claim = next(
        event
        for event in events
        if "Rollback cannot restore" in json.dumps(event.payload)
    )
    print(f"\nThe false rollback claim is event seq={false_claim.logical_seq}, "
          f"recorded {false_claim.logical_seq - verification.logical_seq} "
          "events after the verification read.")

    print(f"\nVisual DAG: uv run casuality-explorer --db {args.db}")

    store.close()


if __name__ == "__main__":
    main()
