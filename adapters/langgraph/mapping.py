"""Map LangGraph execution callbacks into Agent-Causality causal events.

LangGraph (through the LangChain runnable protocol) reports every node, tool,
LLM, and retriever invocation through callback handlers carrying a ``run_id``
(one invocation) and ``parent_run_id`` (the invocation that contained it).
Containment is not causality, so this adapter synthesizes causal edges from
recorded execution order instead:

- one root callback (``parent_run_id`` is None) opens one agent run named
  ``langgraph:<root run id>`` with its own Lamport clock;
- a callback whose causal parent was never observed is dropped: mid-run
  attachment never invents edges;
- every recorded event becomes the frontier of its own run and of its
  parent's run, so sequential siblings chain in the order they executed.

The handler is fail-open: capture errors are collected on ``errors`` and never
propagate into the graph. Payloads are coerced to JSON-safe primitives and
redacted before storage.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from adapters.redaction import redact_value
from sdk.events import AgentClock, Event, record_event
from sdk.memory import ResourceRegistry
from sdk.privacy import PayloadRedactor, make_fail_open_append

try:  # pragma: no cover - both branches are exercised across environments
    from langchain_core.callbacks import BaseCallbackHandler as _BaseCallbackHandler
except ImportError:  # pragma: no cover - LangChain is an optional dependency

    class _BaseCallbackHandler:  # type: ignore[no-redef]
        """Stand-in base so the adapter imports without LangChain installed."""

        raise_error = False


_KIND_CHAIN = "chain"
_KIND_TOOL = "tool"
_KIND_LLM = "llm"
_KIND_RETRIEVER = "retriever"

_PATH_KEYS = ("file_path", "filePath", "path", "filename", "file")
_WRITE_TOOL_RE = re.compile(r"(?:write|edit|create|save|append|patch|mkdir|touch)", re.I)
_MAX_VALUE_CHARS = 4000
_MAX_DEPTH = 8


def _stringify(value: Any, limit: int = _MAX_VALUE_CHARS) -> str:
    """Return a bounded string form for values that cannot stay structured."""
    if isinstance(value, str):
        text = value
    elif isinstance(value, BaseException):
        text = str(value) or repr(value)
    elif isinstance(value, (bytes, bytearray)):
        text = bytes(value).decode("utf-8", "replace")
    else:
        text = repr(value)
    if len(text) > limit:
        text = f"{text[:limit]}...[truncated {len(text) - limit} chars]"
    return text


def _type_name(value: Any) -> str:
    name = getattr(value, "type", None)
    return name if isinstance(name, str) and name else type(value).__name__


def _brief_message(value: Any, redactor: PayloadRedactor, depth: int) -> dict[str, Any] | None:
    """Summarize a LangChain message-like object (content plus routing fields)."""
    content = getattr(value, "content", None)
    if content is None:
        return None
    brief: dict[str, Any] = {"type": _type_name(value)}
    tool_calls = getattr(value, "tool_calls", None)
    if tool_calls:
        brief["tool_calls"] = _jsonable(tool_calls, redactor, depth + 1)
    for attr in ("tool_call_id", "name", "status"):
        nested = getattr(value, attr, None)
        if isinstance(nested, str) and nested:
            brief[attr] = nested
    brief["content"] = _jsonable(content, redactor, depth + 1)
    return brief


def _jsonable(value: Any, redactor: PayloadRedactor, depth: int = 0) -> Any:
    """Coerce an arbitrary callback value into JSON-safe, redacted primitives."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _stringify(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return _stringify(value)
    if depth >= _MAX_DEPTH:
        return _stringify(value, limit=500)
    if isinstance(value, dict):
        coerced = {
            str(key): _jsonable(nested, redactor, depth + 1) for key, nested in value.items()
        }
        return redact_value(coerced, redactor)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item, redactor, depth + 1) for item in value]
    brief = _brief_message(value, redactor, depth)
    if brief is not None:
        return brief
    message = getattr(value, "message", None)
    if message is not None:
        nested = _brief_message(message, redactor, depth)
        if nested is not None:
            result: dict[str, Any] = {"type": type(value).__name__, "message": nested}
            text = getattr(value, "text", None)
            if isinstance(text, str):
                result["text"] = _stringify(text)
            return result
    page_content = getattr(value, "page_content", None)
    if page_content is not None:
        return {
            "type": type(value).__name__,
            "content": _jsonable(page_content, redactor, depth + 1),
        }
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return {"type": type(value).__name__, "text": _stringify(text)}
    return _stringify(value, limit=500)


def _run_name(serialized: Any, name: Any = None, metadata: Any = None) -> str | None:
    """Resolve a human-readable run name from every shape LangChain uses."""
    if isinstance(name, str) and name:
        return name
    if isinstance(serialized, dict):
        candidate = serialized.get("name")
        if isinstance(candidate, str) and candidate:
            return candidate
        identifier = serialized.get("id")
        if isinstance(identifier, (list, tuple)) and identifier:
            return str(identifier[-1])
        if isinstance(identifier, str) and identifier:
            return identifier
    if isinstance(metadata, dict):
        node = metadata.get("langgraph_node")
        if isinstance(node, str) and node:
            return node
    return None


def _unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in ids:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _parse_tool_input(value: Any) -> Any:
    """Normalize a JSON-object tool input string into its dict form."""
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError):
                return value
            return parsed
    return value


def _tool_path(value: Any) -> str | None:
    """Extract a file path from tool arguments (dict, or JSON object string)."""
    value = _parse_tool_input(value)
    if isinstance(value, dict):
        for key in _PATH_KEYS:
            path = value.get(key)
            if isinstance(path, str) and path:
                return path
    return None


def _is_write_tool(name: str | None) -> bool:
    return bool(name and _WRITE_TOOL_RE.search(name))


def _llm_result_parts(result: Any) -> dict[str, Any]:
    """Extract raw pieces of an LLMResult for later JSON-safe coercion."""
    parts: dict[str, Any] = {}
    generations = getattr(result, "generations", None)
    if generations is not None:
        parts["generations"] = generations
    llm_output = getattr(result, "llm_output", None)
    if llm_output is not None:
        parts["llm_output"] = llm_output
    if not parts:
        parts["output"] = result
    return parts


@dataclass
class _RunState:
    """Bookkeeping for one in-flight run (chain node, tool, llm, or retriever)."""

    run_id: str
    root_run_id: str
    parent_run_id: str | None
    is_root: bool
    name: str | None = None
    resource_uri: str | None = None
    frontier_id: str | None = None


class CausalityCallbackHandler(_BaseCallbackHandler):  # ty: ignore[unsupported-base]
    """Record LangGraph/LangChain executions as causal events.

    Attach with ``config={"callbacks": [handler]}`` or ``handler.config()``.
    """

    raise_error = False

    def __init__(
        self,
        log: Any,
        *,
        run_id: str = "langgraph",
        agent_prefix: str = "langgraph",
        registry: ResourceRegistry | None = None,
        redactor: PayloadRedactor | None = None,
    ) -> None:
        self.log = make_fail_open_append(log)
        self.run_id = run_id
        self.agent_prefix = agent_prefix
        self.registry = registry or ResourceRegistry()
        self.redactor = redactor or PayloadRedactor(
            extra_keys={"headers", "authorization", "apiKey", "api_key", "accessToken"}
        )
        self.errors: list[str] = []
        self._lock = Lock()
        self._runs: dict[str, _RunState] = {}
        self._clocks: dict[str, AgentClock] = {}

    # ------------------------------------------------------------------ public API

    def config(self, **overrides: Any) -> dict[str, Any]:
        """Return a runnable config that routes callbacks to this handler."""
        return {"callbacks": [self], **overrides}

    def resources(self) -> dict[tuple[str | None, str], Any]:
        return self.registry.all_resources()

    def reset(self) -> None:
        """Forget per-run bookkeeping; already-stored events are untouched."""
        with self._lock:
            self._runs.clear()
            self._clocks.clear()

    # ------------------------------------------------------------------ chain callbacks

    def on_chain_start(
        self,
        serialized: Any,
        inputs: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._start,
            _KIND_CHAIN,
            run_id,
            parent_run_id,
            serialized=serialized,
            tags=tags,
            metadata=metadata,
            name=kwargs.get("name"),
            input_key="inputs",
            input_value=inputs,
        )

    def on_chain_end(
        self,
        outputs: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._end,
            _KIND_CHAIN,
            run_id,
            output=outputs,
            name=kwargs.get("name"),
            tags=tags,
            metadata=metadata,
        )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(self._error, _KIND_CHAIN, run_id, error=error, tags=tags, metadata=metadata)

    # ------------------------------------------------------------------ tool callbacks

    def on_tool_start(
        self,
        serialized: Any,
        input_str: Any = None,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        inputs: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._start,
            _KIND_TOOL,
            run_id,
            parent_run_id,
            serialized=serialized,
            tags=tags,
            metadata=metadata,
            name=kwargs.get("name"),
            input_key="input",
            input_value=inputs if inputs is not None else input_str,
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._end,
            _KIND_TOOL,
            run_id,
            output=output,
            name=kwargs.get("name"),
            tags=tags,
            metadata=metadata,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(self._error, _KIND_TOOL, run_id, error=error, tags=tags, metadata=metadata)

    # ------------------------------------------------------------------ llm callbacks

    def on_llm_start(
        self,
        serialized: Any,
        prompts: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._start,
            _KIND_LLM,
            run_id,
            parent_run_id,
            serialized=serialized,
            tags=tags,
            metadata=metadata,
            name=kwargs.get("name"),
            input_key="prompts",
            input_value=prompts,
        )

    def on_chat_model_start(
        self,
        serialized: Any,
        messages: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._start,
            _KIND_LLM,
            run_id,
            parent_run_id,
            serialized=serialized,
            tags=tags,
            metadata=metadata,
            name=kwargs.get("name"),
            input_key="messages",
            input_value=messages,
        )

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._end,
            _KIND_LLM,
            run_id,
            output=response,
            name=kwargs.get("name"),
            tags=tags,
            metadata=metadata,
        )

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(self._error, _KIND_LLM, run_id, error=error, tags=tags, metadata=metadata)

    # ------------------------------------------------------------------ retriever callbacks

    def on_retriever_start(
        self,
        serialized: Any,
        query: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._start,
            _KIND_RETRIEVER,
            run_id,
            parent_run_id,
            serialized=serialized,
            tags=tags,
            metadata=metadata,
            name=kwargs.get("name"),
            input_key="query",
            input_value=query,
        )

    def on_retriever_end(
        self,
        documents: Any,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(
            self._end,
            _KIND_RETRIEVER,
            run_id,
            output=documents,
            name=kwargs.get("name"),
            tags=tags,
            metadata=metadata,
        )

    def on_retriever_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: Any = None,
        metadata: Any = None,
        **kwargs: Any,
    ) -> None:
        self._guard(self._error, _KIND_RETRIEVER, run_id, error=error, tags=tags, metadata=metadata)

    # ------------------------------------------------------------------ internals

    def _guard(self, callback: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a callback body; telemetry errors must never break the agent."""
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            return None

    def _common_payload(
        self,
        state: _RunState,
        kind: str,
        phase: str,
        name: Any,
        tags: Any,
        metadata: Any,
    ) -> dict[str, Any]:
        return {
            "runtime": "langgraph",
            "callback": kind,
            "phase": phase,
            "run_id": state.run_id,
            "parent_run_id": state.parent_run_id,
            "name": state.name or _run_name(None, name, metadata),
            "tags": list(tags or []),
            "metadata": metadata,
            "node": metadata.get("langgraph_node") if isinstance(metadata, dict) else None,
            "step": metadata.get("langgraph_step") if isinstance(metadata, dict) else None,
        }

    def _start(
        self,
        kind: str,
        run_id: Any,
        parent_run_id: Any,
        *,
        serialized: Any = None,
        tags: Any = None,
        metadata: Any = None,
        name: Any = None,
        input_key: str = "inputs",
        input_value: Any = None,
    ) -> Event | None:
        run_key = str(run_id)
        parent_key = str(parent_run_id) if parent_run_id is not None else None
        resolved = _run_name(serialized, name, metadata)
        with self._lock:
            if run_key in self._runs:
                return None
            if parent_key is None:
                root_key = run_key
                parents: list[str] = []
            else:
                parent_state = self._runs.get(parent_key)
                if parent_state is None:
                    return None
                root_key = parent_state.root_run_id
                parents = [parent_state.frontier_id] if parent_state.frontier_id else []
            agent_id = f"{self.agent_prefix}:{root_key}"
            clock = self._clocks.get(agent_id)
            if clock is None:
                clock = AgentClock()
                self._clocks[agent_id] = clock
            state = _RunState(
                run_id=run_key,
                root_run_id=root_key,
                parent_run_id=parent_key,
                is_root=parent_key is None,
                name=resolved,
            )
            if kind == _KIND_TOOL:
                event_type = "tool_call"
                input_value = _parse_tool_input(input_value)
                path = _tool_path(input_value)
                if path is not None:
                    state.resource_uri = f"file://{path}"
                    if not _is_write_tool(resolved):
                        latest = self.registry.get_latest(state.resource_uri, run_id=self.run_id)
                        if latest is not None:
                            parents = _unique([*parents, latest.last_writer_event_id])
            elif kind == _KIND_LLM:
                event_type = "model_call"
            elif kind == _KIND_CHAIN and state.is_root:
                event_type = "run_start"
            else:
                event_type = "context_update"
            payload = self._common_payload(state, kind, "start", name, tags, metadata)
            payload[input_key] = input_value
            if kind == _KIND_TOOL:
                payload["invocation_id"] = run_key
                if state.resource_uri is not None:
                    payload["resource_uri"] = state.resource_uri
            self._runs[run_key] = state
            event, _ = self._record(
                state, agent_id, clock, kind, "start", event_type, payload, parents
            )
            return event

    def _end(
        self,
        kind: str,
        run_id: Any,
        *,
        output: Any = None,
        name: Any = None,
        tags: Any = None,
        metadata: Any = None,
    ) -> Event | None:
        run_key = str(run_id)
        with self._lock:
            state = self._runs.get(run_key)
            if state is None:
                return None
            agent_id = f"{self.agent_prefix}:{state.root_run_id}"
            clock = self._clocks.get(agent_id)
            if clock is None:
                return None
            parents = [state.frontier_id] if state.frontier_id else []
            if kind == _KIND_TOOL:
                event_type = "tool_result"
            elif kind == _KIND_LLM:
                event_type = "model_call"
            elif kind == _KIND_CHAIN and state.is_root:
                event_type = "run_finish"
            else:
                event_type = "context_update"
            payload = self._common_payload(state, kind, "end", name, tags, metadata)
            if kind == _KIND_TOOL:
                payload["invocation_id"] = run_key
                payload["output"] = output
                if state.resource_uri is not None:
                    payload["resource_uri"] = state.resource_uri
            elif kind == _KIND_LLM:
                payload.update(_llm_result_parts(output))
            elif kind == _KIND_RETRIEVER:
                payload["documents"] = output
            else:
                payload["output"] = output
            event, stored = self._record(
                state, agent_id, clock, kind, "end", event_type, payload, parents
            )
            if stored and kind == _KIND_TOOL and state.resource_uri is not None:
                if _is_write_tool(state.name):
                    self.registry.register_write(
                        resource_uri=state.resource_uri,
                        writer_event_id=event.id,
                        writer_agent_id=event.agent_id,
                        logical_seq=event.logical_seq,
                        wall_time=event.wall_time,
                        run_id=self.run_id,
                    )
            if state.is_root:
                self._prune_locked(state.root_run_id)
            return event

    def _error(
        self,
        kind: str,
        run_id: Any,
        *,
        error: BaseException,
        name: Any = None,
        tags: Any = None,
        metadata: Any = None,
    ) -> Event | None:
        run_key = str(run_id)
        message = _stringify(error)
        with self._lock:
            state = self._runs.get(run_key)
            if state is None:
                return None
            agent_id = f"{self.agent_prefix}:{state.root_run_id}"
            clock = self._clocks.get(agent_id)
            if clock is None:
                return None
            parents = [state.frontier_id] if state.frontier_id else []
            # A failed tool still closes its open invocation; every other
            # failure marks the agent as errored, which is what the reducer
            # records for agent_error.
            event_type = "tool_result" if kind == _KIND_TOOL else "agent_error"
            payload = self._common_payload(state, kind, "error", name, tags, metadata)
            payload["error"] = message
            payload["error_type"] = type(error).__name__
            if kind == _KIND_TOOL:
                payload["invocation_id"] = run_key
                payload["output"] = {"error": message, "error_type": type(error).__name__}
                if state.resource_uri is not None:
                    payload["resource_uri"] = state.resource_uri
            event, _ = self._record(
                state, agent_id, clock, kind, "error", event_type, payload, parents
            )
            if state.is_root:
                self._prune_locked(state.root_run_id)
            return event

    def _record(
        self,
        state: _RunState,
        agent_id: str,
        clock: AgentClock,
        kind: str,
        phase: str,
        event_type: str,
        payload: dict[str, Any],
        parents: list[str],
    ) -> tuple[Event, bool]:
        idempotency_key = f"langgraph:{kind}:{phase}:{state.run_id}"
        event, stored = record_event(
            agent_id=agent_id,
            clock=clock,
            log=self.log,
            event_type=event_type,
            payload=_jsonable(payload, self.redactor),
            causal_parent_ids=parents,
            run_id=self.run_id,
            idempotency_key=idempotency_key,
            event_id=str(uuid5(NAMESPACE_URL, idempotency_key)),
        )
        if stored:
            self._advance(state, event)
        return event, stored

    def _advance(self, state: _RunState, event: Event) -> None:
        """Make the recorded event the frontier of its own and its parent's run."""
        state.frontier_id = event.id
        if state.parent_run_id is None:
            return
        parent_state = self._runs.get(state.parent_run_id)
        if parent_state is not None:
            parent_state.frontier_id = event.id

    def _prune_locked(self, root_key: str) -> None:
        """Drop finished runs; the stored events remain the record of truth."""
        for key in [key for key, state in self._runs.items() if state.root_run_id == root_key]:
            self._runs.pop(key, None)
        self._clocks.pop(f"{self.agent_prefix}:{root_key}", None)
