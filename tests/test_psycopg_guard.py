"""Behavior of the optional psycopg import boundary."""

from __future__ import annotations

import sys

import pytest

from storage._psycopg import load_psycopg_or_skip


def test_load_psycopg_or_skip_returns_installed_driver() -> None:
    psycopg = load_psycopg_or_skip()

    assert hasattr(psycopg, "connect")


def test_load_psycopg_or_skip_skips_missing_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "psycopg", None)

    with pytest.raises(pytest.skip.Exception):
        load_psycopg_or_skip()
