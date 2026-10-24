"""Run one coding task in an isolated git worktree with a concurrency cap.

Usage:
    uv run python tools/agents/spawn.py --task "..." --branch agent/task-name

The worktree is created under tools/agents/worktrees/ (gitignored). Setup runs
uv sync and npm ci there, then `opencode run` works on the task. The script runs
the full verify CLI itself and exits 0 only when that passes. Merge and push are
off by default; pass --merge or --push to opt in.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "tools" / "agents"
WORKTREES = AGENTS / "worktrees"
LOGS = AGENTS / "logs"
STATE = AGENTS / "state"
DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"
MAX_CONCURRENT = 3
STALE_AFTER_SECONDS = 12 * 60 * 60


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in completed.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _stale(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        pid = int(data["pid"])
        created = float(data["created"])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return time.time() - created > STALE_AFTER_SECONDS or not _pid_alive(pid)


@contextmanager
def _slot(max_concurrent: int) -> Iterator[int]:
    STATE.mkdir(parents=True, exist_ok=True)
    waiting = False
    while True:
        for index in range(max_concurrent):
            path = STATE / f"slot-{index}.lock"
            try:
                handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if _stale(path):
                    path.unlink(missing_ok=True)
                continue
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "created": time.time()}, stream)
            try:
                yield index
            finally:
                path.unlink(missing_ok=True)
            return
        if not waiting:
            print(f"waiting for a free slot (max {max_concurrent})...", flush=True)
            waiting = True
        time.sleep(1)


def _run(
    command: list[str],
    cwd: Path,
    log_path: Path,
    timeout: int,
) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = shutil.which(command[0])
    if resolved is not None:
        command = [resolved, *command[1:]]
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(command)}\n")
        log.flush()
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
            code = completed.returncode
        except subprocess.TimeoutExpired:
            log.write(f"\n[spawn] timed out after {timeout}s\n")
            code = 124
    return code


def _task_prompt(task: str, branch: str, worktree: Path) -> str:
    return f"""You are working in an isolated git worktree: {worktree}
Branch: {branch}

Task:
{task}

Rules:
- Implement only this task. Do not edit files outside this worktree.
- Run `uv run python tools/verify/verify.py` (full mode) before finishing.
- If it passes, commit your changes on this branch with a descriptive message.
- If it fails, leave the worktree in place and report FAIL with the failing step.
- Do not push or merge. Do not edit generated files; use the sync scripts.
"""


def _summary(
    log_dir: Path,
    branch: str,
    worktree: Path,
    task: str,
    agent_code: int,
    verify_code: int,
) -> dict[str, object]:
    data = {
        "branch": branch,
        "worktree": str(worktree),
        "task": task,
        "agent_exit": agent_code,
        "verify_exit": verify_code,
        "passed": agent_code == 0 and verify_code == 0,
        "finished": datetime.now(UTC).isoformat(),
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "summary.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spawn an agent in a git worktree")
    parser.add_argument("--task", required=True, help="task description for the agent")
    parser.add_argument("--branch", required=True, help="new branch name")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="provider/model")
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT, choices=[1, 2, 3])
    parser.add_argument("--agent-timeout", type=int, default=3600)
    parser.add_argument("--verify-timeout", type=int, default=900)
    parser.add_argument("--merge", action="store_true", help="merge the branch after PASS")
    parser.add_argument("--push", action="store_true", help="push the branch after PASS")
    args = parser.parse_args(argv)

    branch_slug = _slug(args.branch)
    worktree = WORKTREES / branch_slug
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_dir = LOGS / f"{stamp}-{branch_slug}"

    with _slot(args.max_concurrent):
        print(f"slot acquired for {args.branch}", flush=True)
        try:
            if worktree.exists():
                raise RuntimeError(f"worktree already exists: {worktree}")
            WORKTREES.mkdir(parents=True, exist_ok=True)
            log_dir.mkdir(parents=True, exist_ok=True)
            setup_log = log_dir / "setup.log"
            agent_log = log_dir / "agent.log"
            verify_log = log_dir / "verify.log"

            code = _run(
                ["git", "worktree", "add", "-b", args.branch, str(worktree), args.base],
                ROOT,
                setup_log,
                120,
            )
            if code != 0:
                raise RuntimeError(f"git worktree add failed; see {setup_log}")
            for command in (
                ["uv", "sync"],
                ["npm", "ci", "--prefix", "frontend"],
                ["npm", "ci", "--prefix", "packages/opencode-agent-causality"],
            ):
                code = _run(command, worktree, setup_log, 600)
                if code != 0:
                    raise RuntimeError(f"setup failed: {' '.join(command)}; see {setup_log}")

            agent_code = _run(
                [
                    "opencode",
                    "run",
                    "--standalone",
                    "--auto",
                    "--model",
                    args.model,
                    "--title",
                    f"{args.branch}: {args.task[:60]}",
                    _task_prompt(args.task, args.branch, worktree),
                ],
                worktree,
                agent_log,
                args.agent_timeout,
            )
            verify_code = _run(
                ["uv", "run", "python", "tools/verify/verify.py"],
                worktree,
                verify_log,
                args.verify_timeout,
            )
            data = _summary(log_dir, args.branch, worktree, args.task, agent_code, verify_code)
            status = "PASS" if data["passed"] else "FAIL"
            print(f"{status} {args.branch}  logs: {log_dir}", flush=True)
            if not data["passed"]:
                return 1

            if args.push:
                code = _run(
                    ["git", "push", "-u", "origin", args.branch],
                    worktree,
                    log_dir / "push.log",
                    300,
                )
                if code != 0:
                    print(f"FAIL push {args.branch}", flush=True)
                    return 1
            if args.merge:
                code = _run(
                    ["git", "merge", "--no-ff", args.branch],
                    ROOT,
                    log_dir / "merge.log",
                    300,
                )
                if code != 0:
                    print(f"FAIL merge {args.branch}", flush=True)
                    return 1
            return 0
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            print(f"FAIL {args.branch}: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
