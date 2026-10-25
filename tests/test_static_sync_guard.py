from __future__ import annotations

from tools.verify import static_sync_guard as guard


def test_main_checkout_passes(monkeypatch) -> None:
    monkeypatch.setattr(guard, "_is_linked_worktree", lambda: False)

    assert guard.main() == 0


def test_linked_worktree_with_staged_assets_fails(monkeypatch, capsys) -> None:
    monkeypatch.setattr(guard, "_is_linked_worktree", lambda: True)
    monkeypatch.setattr(
        guard, "_staged_static", lambda: ["explorer/static/index.html"]
    )

    assert guard.main() == 1
    assert "staged from a linked worktree" in capsys.readouterr().err


def test_linked_worktree_without_staged_assets_passes(monkeypatch) -> None:
    monkeypatch.setattr(guard, "_is_linked_worktree", lambda: True)
    monkeypatch.setattr(guard, "_staged_static", lambda: [])

    assert guard.main() == 0
