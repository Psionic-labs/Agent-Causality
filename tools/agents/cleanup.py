"""List and remove agent worktrees that are merged or abandoned.

A worktree is a cleanup candidate when its branch is already merged into the
base branch, or when its last commit is older than ``--older-than`` days.
Removal always asks for confirmation unless ``--yes`` is passed.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKTREES = ROOT / "tools" / "agents" / "worktrees"
DEFAULT_OLDER_THAN_DAYS = 7


@dataclass
class Worktree:
    path: Path
    branch: str | None
    head: str
    last_commit: float
    merged: bool
    dirty: bool
    missing: bool
    age_days: float
    older_than_days: float

    @property
    def abandoned(self) -> bool:
        return not self.merged and self.age_days > self.older_than_days

    @property
    def candidate(self) -> bool:
        return self.missing or self.merged or self.abandoned

    @property
    def reason(self) -> str:
        if self.missing:
            return "missing"
        if self.merged:
            return "merged"
        if self.abandoned:
            return f"abandoned {self.age_days:.1f}d"
        return "active"


def _git(*args: str, cwd: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def _worktrees(base: str, older_than_days: float) -> list[Worktree]:
    listing = _git("worktree", "list", "--porcelain")
    if listing.returncode != 0:
        raise RuntimeError(listing.stderr.strip() or "git worktree list failed")
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in listing.stdout.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)

    now = time.time()
    result: list[Worktree] = []
    for entry in entries:
        raw_path = entry.get("worktree")
        if raw_path is None:
            continue
        path = Path(raw_path)
        try:
            path.relative_to(WORKTREES)
        except ValueError:
            continue
        head = entry.get("HEAD", "")
        branch_ref = entry.get("branch")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else None
        missing = not path.is_dir()
        last_commit = _last_commit(head)
        age_days = max(0.0, (now - last_commit) / 86400) if last_commit else 0.0
        result.append(
            Worktree(
                path=path,
                branch=branch,
                head=head,
                last_commit=last_commit,
                merged=_is_merged(head, base),
                dirty=False if missing else _is_dirty(path),
                missing=missing,
                age_days=age_days,
                older_than_days=older_than_days,
            )
        )
    return result


def _last_commit(rev: str) -> float:
    if not rev:
        return 0.0
    completed = _git("log", "-1", "--format=%ct", rev)
    if completed.returncode != 0:
        return 0.0
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return 0.0


def _is_merged(head: str, base: str) -> bool:
    if not head:
        return False
    return _git("merge-base", "--is-ancestor", head, base).returncode == 0


def _is_dirty(path: Path) -> bool:
    completed = _git("status", "--porcelain", cwd=path)
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _format_age(timestamp: float) -> str:
    if not timestamp:
        return "unknown"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _show(worktrees: list[Worktree]) -> None:
    if not worktrees:
        print("no agent worktrees")
        return
    print(f"{'STATUS':<14} {'BRANCH':<32} {'LAST COMMIT':<17} PATH")
    for worktree in worktrees:
        branch = worktree.branch or "(detached)"
        print(
            f"{worktree.reason:<14} {branch:<32} "
            f"{_format_age(worktree.last_commit):<17} {worktree.path}"
        )


def _remove(worktree: Worktree, *, force: bool) -> bool:
    if worktree.missing:
        pruned = _git("worktree", "prune")
        if pruned.returncode != 0:
            print(f"FAIL prune: {pruned.stderr.strip()}")
            return False
    else:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree.path))
        completed = _git(*args)
        if completed.returncode != 0:
            print(f"FAIL remove {worktree.path}: {completed.stderr.strip()}")
            return False
    if worktree.branch:
        flag = "-d" if worktree.merged else "-D"
        deleted = _git("branch", flag, worktree.branch)
        if deleted.returncode != 0:
            print(f"WARN branch not deleted {worktree.branch}: {deleted.stderr.strip()}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean up agent worktrees")
    parser.add_argument("--list", action="store_true", help="list worktrees and exit")
    parser.add_argument("--yes", action="store_true", help="remove without prompting")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument(
        "--older-than",
        type=float,
        default=DEFAULT_OLDER_THAN_DAYS,
        help="days without a commit before a worktree counts as abandoned",
    )
    parser.add_argument("--force", action="store_true", help="remove dirty worktrees too")
    args = parser.parse_args(argv)

    if _git("rev-parse", "--verify", args.base).returncode != 0:
        print(f"FAIL base branch not found: {args.base}")
        return 1

    worktrees = _worktrees(args.base, args.older_than)
    _show(worktrees)
    if args.list:
        return 0

    candidates = [worktree for worktree in worktrees if worktree.candidate]
    if not candidates:
        print("\nnothing to remove")
        return 0

    blocked = [worktree for worktree in candidates if worktree.dirty and not args.force]
    removable = [worktree for worktree in candidates if worktree not in blocked]
    if blocked:
        print("\nskipping dirty worktrees (pass --force to remove):")
        for worktree in blocked:
            print(f"  {worktree.path}")
    if not removable:
        return 1

    print(f"\n{len(removable)} worktree(s) can be removed:")
    for worktree in removable:
        print(f"  {worktree.reason:<14} {worktree.branch or '(detached)'}")
    if not args.yes:
        answer = input("Remove them? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("aborted")
            return 1

    failed = 0
    for worktree in removable:
        if _remove(worktree, force=args.force):
            print(f"removed {worktree.path}")
        else:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
