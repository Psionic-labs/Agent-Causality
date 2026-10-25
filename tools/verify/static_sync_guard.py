"""Reject generated Explorer assets staged from a linked git worktree.

A Next.js build embeds checkout-dependent module IDs, so syncing from a
worktree produces a bundle that does not match the main checkout. Only the
main checkout may commit ``explorer/static``; worktree agents use the input
manifest instead.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _is_linked_worktree() -> bool:
    git_dir = _git("rev-parse", "--git-dir")
    common_dir = _git("rev-parse", "--git-common-dir")
    if git_dir.returncode != 0 or common_dir.returncode != 0:
        raise RuntimeError("not a git checkout")
    return Path(git_dir.stdout.strip()).resolve() != Path(common_dir.stdout.strip()).resolve()


def _staged_static() -> list[str]:
    completed = _git("diff", "--cached", "--name-only", "--", "explorer/static")
    if completed.returncode != 0:
        raise RuntimeError("git diff --cached failed")
    return [line for line in completed.stdout.splitlines() if line]


def main() -> int:
    try:
        linked = _is_linked_worktree()
        staged = _staged_static() if linked else []
    except RuntimeError as exc:
        print(f"FAIL static sync guard: {exc}", file=sys.stderr)
        return 1
    if not linked:
        print("PASS static sync guard (main checkout)")
        return 0
    if staged:
        print(
            "FAIL static sync guard: explorer/static/ is staged from a linked worktree. "
            "Build and sync in the main checkout; worktree agents must not commit "
            "generated Explorer assets.",
            file=sys.stderr,
        )
        for path in staged:
            print(f"  {path}", file=sys.stderr)
        return 1
    print("PASS static sync guard (linked worktree, no generated assets staged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
