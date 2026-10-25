"""Capture-completeness scoring for the real OpenCode benchmark.

Diagnosis scoring lives in :mod:`core.diagnosis` so the explorer can reuse it
without importing benchmark code. This module only classifies captured events
and measures expected event-class coverage; nothing here runs OpenCode.
"""

from __future__ import annotations

import json
from typing import Any

from core.diagnosis import event_inner_payload, event_payload

EVENT_CLASSES = (
    "sessions",
    "model_calls",
    "tool_calls",
    "tool_results",
    "file_edits",
    "commands",
    "errors",
    "retries",
    "subagents",
    "completion",
)


def classify_event(event: Any) -> set[str]:
    """Return the observable classes one captured event belongs to."""
    kind = str(event_payload(event).get("opencode_kind", ""))
    inner = event_inner_payload(event)
    classes: set[str] = set()
    if kind in {
        "event:session.created",
        "session.created",
        "event:session.deleted",
        "session.deleted",
    }:
        classes.add("sessions")
    if kind in {"event:message.updated", "message.updated"}:
        classes.add("model_calls")
    if kind in {"hook:tool.execute.before", "tool.execute.before"}:
        classes.add("tool_calls")
        tool_name = str(inner.get("tool", "")).lower()
        args = inner.get("args", {})
        if tool_name == "task" or (
            isinstance(args, dict)
            and "subagent" in json.dumps(args, default=str).lower()
        ):
            classes.add("subagents")
        # Shell executions are the observable form of commands/tests:
        # OpenCode emits command.executed only for slash-commands, while
        # `python test_x.py` runs through the bash tool.
        if tool_name in {"bash", "shell"} or (
            isinstance(args, dict) and "command" in args
        ):
            classes.add("commands")
    if kind in {"hook:tool.execute.after", "tool.execute.after"}:
        classes.add("tool_results")
        tool_name = str(inner.get("tool", "")).lower()
        if tool_name in {"bash", "shell"}:
            classes.add("commands")
    if kind in {"event:file.edited", "file.edited"}:
        classes.add("file_edits")
    if kind in {
        "event:command.executed",
        "command.executed",
        "hook:command.execute.before",
    }:
        classes.add("commands")
    if kind in {"event:session.error", "session.error"}:
        classes.add("errors")
    if kind in {"event:message.part.updated", "message.part.updated"}:
        part = inner.get("part", {})
        if isinstance(part, dict) and str(part.get("type", "")).lower() in {
            "retry",
            "subtask",
            "agent",
        }:
            if str(part.get("type", "")).lower() == "retry":
                classes.add("retries")
            else:
                classes.add("subagents")
    if kind in {"event:session.status", "session.status"}:
        status = inner.get("status", {})
        if isinstance(status, dict) and str(status.get("type", "")).lower() == "retry":
            classes.add("retries")
    if kind in {
        "event:session.deleted",
        "session.deleted",
        "event:session.idle",
        "session.idle",
    }:
        classes.add("completion")
    return classes


def _command_signature(event: Any) -> str | None:
    inner = event_inner_payload(event)
    name = inner.get("name") or inner.get("command") or inner.get("tool")
    args = inner.get("arguments", "")
    if isinstance(inner.get("args"), dict):
        args = inner["args"].get("command", args)
    if name:
        return f"{name} {args}".strip()
    return None


def capture_completeness(
    events: list[Any], expected: dict[str, Any]
) -> dict[str, Any]:
    """Score minimum expected event-class coverage per observable class.

    This is NOT general event precision/recall. Each class contributes
    ``min(1, captured / expected_min)`` and the overall figure is the mean
    over classes with ``available == True`` and ``min > 0`` only.
    Classes with min == 0 are reported informationally and excluded from
    the overall average, as are classes marked unavailable from OpenCode
    (e.g. terminal ``completion`` events in ``run`` mode). Repeat
    executions of the same command count as retries (in addition to
    explicit retry parts).
    """
    counts: dict[str, int] = {name: 0 for name in EVENT_CLASSES}
    file_edit_files: list[str] = []
    command_events = 0
    seen_signatures: set[str] = set()
    repeat_commands = 0
    for event in events:
        classes = classify_event(event)
        for name in classes:
            counts[name] += 1
        if "file_edits" in classes:
            uri = str(event_payload(event).get("resource_uri", ""))
            file_edit_files.append(uri)
        if "commands" in classes:
            command_events += 1
            sig = _command_signature(event)
            if sig is not None:
                if sig in seen_signatures:
                    repeat_commands += 1
                seen_signatures.add(sig)
    counts["retries"] += repeat_commands

    per_class: dict[str, Any] = {}
    recalls: list[float] = []
    class_names = list(EVENT_CLASSES) + [
        name for name in expected if name not in EVENT_CLASSES
    ]
    for name in class_names:
        spec = expected.get(name, {"min": 0, "available": True})
        minimum = int(spec.get("min", 0))
        available = bool(spec.get("available", True))
        captured = counts.get(name, 0)
        missing = max(0, minimum - captured) if available else 0
        recall = 1.0 if minimum == 0 else min(1.0, captured / minimum)
        if available and minimum > 0:
            recalls.append(recall)
        per_class[name] = {
            "expected_min": minimum,
            "available": available,
            "captured": captured,
            "missing": missing,
            "recall": round(recall, 3),
        }
    overall = round(sum(recalls) / len(recalls), 3) if recalls else 1.0
    return {
        "metric": "minimum_expected_event_class_coverage",
        "per_class": per_class,
        "command_count": command_events,
        "repeat_command_retries": repeat_commands,
        "file_edit_resources": file_edit_files,
        "overall_recall": overall,
        "overall_coverage": overall,
        "scored_classes": len(recalls),
    }
