from __future__ import annotations

import json
from typing import Any, TypedDict, cast
from uuid import uuid4

from adapters.langgraph.mapping import CasualityCallbackHandler
from core.reducer import AgentState, reduce
from core.validator import GraphValidator
from sdk.events import InMemoryEventLog
from storage.sqlite import SQLiteEventStore


class _GraphState(TypedDict):
    value: int


def _reduce_all(log: InMemoryEventLog) -> AgentState:
    state = AgentState.empty()
    for event in log.events():
        state = reduce(state, event)
    return state


def test_root_chain_start_and_end_chain_together() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root = uuid4()

    handler.on_chain_start({"name": "graph"}, {"x": 1}, run_id=root)
    handler.on_chain_end({"y": 2}, run_id=root)

    events = log.events()
    assert [event.event_type for event in events] == ["run_start", "run_finish"]
    start, finish = events
    assert start.agent_id == f"langgraph:{root}"
    assert start.causal_parent_ids == []
    assert finish.causal_parent_ids == [start.id]
    assert finish.run_id == "langgraph"
    assert start.payload["runtime"] == "langgraph"
    assert start.payload["callback"] == "chain"
    assert start.payload["name"] == "graph"
    assert start.payload["inputs"] == {"x": 1}
    assert finish.payload["output"] == {"y": 2}
    assert handler.errors == []


def test_node_and_tool_events_form_valid_chain() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root, node, tool = uuid4(), uuid4(), uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_chain_start({"name": "planner"}, {}, run_id=node, parent_run_id=root)
    handler.on_tool_start({"name": "search"}, "query", run_id=tool, parent_run_id=node)
    handler.on_tool_end("results", run_id=tool)
    handler.on_chain_end({"plan": "done"}, run_id=node)
    handler.on_chain_end({"answer": 42}, run_id=root)

    events = log.events()
    assert [event.event_type for event in events] == [
        "run_start",
        "context_update",
        "tool_call",
        "tool_result",
        "context_update",
        "run_finish",
    ]
    for index, event in enumerate(events):
        assert event.agent_id == f"langgraph:{root}"
        if index == 0:
            assert event.causal_parent_ids == []
        else:
            assert event.causal_parent_ids == [events[index - 1].id]
    assert events[2].payload["invocation_id"] == str(tool)
    assert events[2].payload["input"] == "query"
    assert events[3].payload["invocation_id"] == str(tool)
    assert events[3].payload["output"] == "results"
    assert events[1].payload["name"] == "planner"

    report = GraphValidator(log).validate_run("langgraph")
    assert report.is_valid, report.violations
    assert report.warnings == []


def test_unknown_parent_events_are_dropped() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)

    handler.on_chain_start({"name": "node"}, {}, run_id=uuid4(), parent_run_id=uuid4())
    handler.on_tool_end("x", run_id=uuid4())
    handler.on_llm_end(None, run_id=uuid4())

    assert log.events() == []
    assert handler.errors == []


def test_duplicate_start_is_idempotent() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root = uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_chain_start({"name": "graph"}, {}, run_id=root)

    assert len(log.events()) == 1


def test_multiple_invocations_get_isolated_agents() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    first, second = uuid4(), uuid4()

    handler.on_chain_start({"name": "first"}, {}, run_id=first)
    handler.on_chain_end({}, run_id=first)
    handler.on_chain_start({"name": "second"}, {}, run_id=second)
    handler.on_chain_end({}, run_id=second)

    events = log.events()
    assert {event.agent_id for event in events} == {
        f"langgraph:{first}",
        f"langgraph:{second}",
    }
    report = GraphValidator(log).validate_run("langgraph")
    assert report.is_valid, report.violations


def test_tool_failure_closes_open_invocation() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root, tool = uuid4(), uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_tool_start({"name": "search"}, "q", run_id=tool, parent_run_id=root)
    handler.on_tool_error(RuntimeError("kaput"), run_id=tool)

    events = log.events()
    assert events[-1].event_type == "tool_result"
    assert events[-1].payload["error_type"] == "RuntimeError"
    assert events[-1].payload["output"] == {"error": "kaput", "error_type": "RuntimeError"}

    state = _reduce_all(log)
    assert state.open_tools == {}
    assert state.tool_outputs[str(tool)] == {"error": "kaput", "error_type": "RuntimeError"}


def test_llm_error_marks_agent_error() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root, llm = uuid4(), uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_llm_start({"name": "FakeLLM"}, ["prompt"], run_id=llm, parent_run_id=root)
    handler.on_llm_error(ValueError("rate limited"), run_id=llm)

    events = log.events()
    assert events[-1].event_type == "agent_error"
    assert events[-1].payload["error_type"] == "ValueError"
    state = _reduce_all(log)
    assert state.status == "error"


def test_llm_start_and_end_record_model_calls() -> None:
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root, llm = uuid4(), uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_chat_model_start(
        {"name": "ChatFake"},
        [[HumanMessage(content="hi")]],
        run_id=llm,
        parent_run_id=root,
    )
    handler.on_llm_end(
        LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="pong"))]],
            llm_output={"token_usage": 3},
        ),
        run_id=llm,
    )

    events = log.events()
    assert [event.event_type for event in events] == ["run_start", "model_call", "model_call"]
    assert events[1].payload["messages"][0][0] == {"type": "human", "content": "hi"}
    generation = events[2].payload["generations"][0][0]
    assert generation["message"]["type"] == "ai"
    assert generation["message"]["content"] == "pong"
    assert events[2].payload["llm_output"] == {"token_usage": 3}


def test_write_then_read_tool_links_writer_as_parent() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root, write, read = uuid4(), uuid4(), uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_tool_start(
        {"name": "write_file"},
        json.dumps({"file_path": "notes.md", "content": "hi"}),
        run_id=write,
        parent_run_id=root,
    )
    handler.on_tool_end("saved", run_id=write)
    handler.on_tool_start(
        {"name": "read_file"},
        json.dumps({"file_path": "notes.md"}),
        run_id=read,
        parent_run_id=root,
    )

    events = log.events()
    write_end = next(event for event in events if event.event_type == "tool_result")
    read_start = next(
        event for event in events if event.payload.get("name") == "read_file"
    )
    assert read_start.causal_parent_ids == [write_end.id]
    assert write_end.payload["resource_uri"] == "file://notes.md"
    assert read_start.payload["resource_uri"] == "file://notes.md"

    resources = handler.resources()
    assert ("langgraph", "file://notes.md") in resources
    entry = resources[("langgraph", "file://notes.md")]
    assert entry.last_writer_event_id == write_end.id

    report = GraphValidator(log).validate_run("langgraph")
    assert report.is_valid, report.violations


def test_payloads_are_redacted_and_json_safe(tmp_path) -> None:
    log = SQLiteEventStore(tmp_path / "events.db")
    handler = CasualityCallbackHandler(log)

    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    root, tool = uuid4(), uuid4()
    handler.on_chain_start(
        {"name": "graph"},
        {"api_key": "sk-secret", "blob": Opaque()},
        run_id=root,
    )
    handler.on_tool_start(
        {"name": "search"},
        json.dumps({"file_path": "a.md", "authorization": "Bearer tok"}),
        run_id=tool,
        parent_run_id=root,
    )

    events = log.events()
    assert len(events) == 2
    start, tool_call = events
    assert start.payload["inputs"]["api_key"] == "[REDACTED]"
    assert start.payload["inputs"]["blob"] == "<opaque>"
    dumped = json.dumps(start.payload)
    assert "sk-secret" not in dumped
    assert tool_call.payload["input"]["authorization"] == "[REDACTED]"


def test_long_values_are_truncated() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root = uuid4()

    handler.on_chain_start({"name": "graph"}, {"text": "x" * 10_000}, run_id=root)

    text = log.events()[0].payload["inputs"]["text"]
    assert text.endswith("...[truncated 6000 chars]")
    assert len(text) < 4_100


def test_config_returns_callback_config() -> None:
    handler = CasualityCallbackHandler(InMemoryEventLog())

    config = handler.config()
    assert config["callbacks"] == [handler]
    assert handler.config(recursion_limit=5)["recursion_limit"] == 5


def test_capture_survives_store_failure() -> None:
    class ExplodingLog:
        def append(self, event: Any) -> Any:
            raise RuntimeError("disk full")

        def get_by_idempotency_key(self, agent_id: str, key: str) -> None:
            return None

    handler = CasualityCallbackHandler(ExplodingLog())
    root = uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.on_chain_end({}, run_id=root)

    assert handler.errors == []


def test_reset_drops_run_state() -> None:
    log = InMemoryEventLog()
    handler = CasualityCallbackHandler(log)
    root = uuid4()

    handler.on_chain_start({"name": "graph"}, {}, run_id=root)
    handler.reset()
    handler.on_chain_end({}, run_id=root)

    assert len(log.events()) == 1


def test_real_langgraph_execution_is_captured(tmp_path) -> None:
    import pytest

    pytest.importorskip("langgraph")
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph

    def increment(state: _GraphState) -> dict[str, int]:
        return {"value": state["value"] + 1}

    def double(state: _GraphState) -> dict[str, int]:
        return {"value": state["value"] * 2}

    builder = StateGraph(_GraphState)  # ty: ignore[invalid-argument-type]
    builder.add_node("increment", increment)
    builder.add_node("double", double)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", "double")
    builder.add_edge("double", END)
    app = builder.compile()

    log = SQLiteEventStore(tmp_path / "langgraph.db")
    handler = CasualityCallbackHandler(log)
    config = cast(RunnableConfig, handler.config())
    result = app.invoke({"value": 1}, config=config)

    assert result == {"value": 4}
    events = log.events()
    assert events, "no events captured"
    types = [event.event_type for event in events]
    assert types[0] == "run_start"
    assert types[-1] == "run_finish"
    assert "context_update" in types
    assert handler.errors == []

    report = GraphValidator(log).validate_run("langgraph")
    assert report.is_valid, report.violations
    assert report.warnings == []

    state = _reduce_all(log)
    assert state.open_tools == {}
    assert state.status == "active"
