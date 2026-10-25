from __future__ import annotations

import os

from scripts.advisory_review import REVIEW_CREDENTIALS, main, select_review_credential


def _clear(monkeypatch) -> None:
    for name, _model in REVIEW_CREDENTIALS:
        monkeypatch.delenv(name, raising=False)


def test_openrouter_key_selects_openrouter_model(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")

    assert select_review_credential(os.environ) == (
        "OPENROUTER_API_KEY",
        "openrouter/deepseek/deepseek-v4-flash",
    )


def test_opencode_key_wins_when_another_key_is_also_set(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENCODE_API_KEY", "oc-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")

    assert select_review_credential(os.environ) == (
        "OPENCODE_API_KEY",
        "opencode/deepseek-v4.1-flash-free",
    )


def test_blank_opencode_key_falls_through_to_openrouter(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("OPENCODE_API_KEY", "   ")
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")

    assert select_review_credential(os.environ) == (
        "OPENROUTER_API_KEY",
        "openrouter/deepseek/deepseek-v4-flash",
    )


def test_no_keys_skips(monkeypatch, capsys) -> None:
    _clear(monkeypatch)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    assert select_review_credential(os.environ) is None
    assert main([]) == 0
    err = capsys.readouterr().err
    assert "skipping the advisory review" in err
    assert "OPENCODE_API_KEY" in err
    assert "OPENROUTER_API_KEY" in err
