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


def load_psycopg_or_skip() -> Any:
    """Return psycopg for an integration test, or skip when it is not installed.

    Test modules ask for the driver here instead of importing psycopg directly,
    so the optional-import boundary stays in one place.
    """
    try:
        import psycopg
    except ImportError:
        import pytest

        pytest.skip(f"psycopg is not installed. {_HINT}")
    return psycopg
