"""The single optional-import boundary for psycopg.

Every other module asks this module for psycopg. That keeps the dependency
optional, gives one install hint, and makes direct imports enforceable.
"""

from __future__ import annotations

from typing import Any

_HINT = "Install the postgres extra: pip install 'agent-causality[postgres]'"


def load_psycopg() -> Any:
    """Return the psycopg module or raise one actionable error."""
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(f"psycopg is required for PostgreSQL storage. {_HINT}") from exc
    return psycopg


def load_jsonb() -> Any:
    """Return psycopg's Jsonb wrapper or raise one actionable error."""
    try:
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError(f"psycopg is required for PostgreSQL storage. {_HINT}") from exc
    return Jsonb
