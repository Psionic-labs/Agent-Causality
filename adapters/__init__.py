"""Runtime capture adapters for Agent-Causality.

Each adapter maps one agent runtime's native observability signals into the
SDK event vocabulary without inferring causality that the runtime did not
expose:

- ``adapters.opencode``: OpenCode plugin envelopes (HTTP ingest receiver).
- ``adapters.langgraph``: LangChain/LangGraph callback events (in-process).
"""
