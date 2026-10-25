from __future__ import annotations

from tools.agents.spawn import _out_of_scope


def test_allowed_directories_and_files_pass() -> None:
    changed = ["core/diagnosis.py", "tests/test_phase2_5.py", "CLEANUP.md"]

    assert _out_of_scope(changed, ["core/", "tests/test_phase2_5.py", "CLEANUP.md"]) == []


def test_paths_outside_the_allowlist_fail() -> None:
    changed = ["core/diagnosis.py", "sdk/tools.py"]

    assert _out_of_scope(changed, ["core/"]) == ["sdk/tools.py"]


def test_empty_allowlist_allows_everything() -> None:
    assert _out_of_scope(["anything/at/all.py"], []) == []
