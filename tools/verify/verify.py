"""Run the repository's deterministic checks and the Explorer smoke test.

Usage:
    uv run python tools/verify/verify.py --quick   # static checks only
    uv run python tools/verify/verify.py           # full: checks + app + browser

Every step writes a log under tools/verify/artifacts/<run>/. Failures print the
tail of the log, and the exit code is non-zero if any step fails.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PLUGIN = ROOT / "packages" / "opencode-agent-causality"
ARTIFACTS = ROOT / "tools" / "verify" / "artifacts"
TAIL_LINES = 40


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    cwd: Path = ROOT
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 600
    must_contain: tuple[str, ...] = ()


@dataclass(frozen=True)
class Result:
    name: str
    passed: bool
    seconds: float
    detail: str
    log: Path


def _tool(name: str) -> str:
    return shutil.which(name) or name


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _display(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join(text.splitlines()[-lines:])


def _env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(extra)
    env.setdefault("NO_COLOR", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _coerce(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_step(step: Step, run_dir: Path) -> Result:
    log_path = run_dir / f"{_slug(step.name)}.log"
    command = (_tool(step.command[0]), *step.command[1:])
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=step.cwd,
            env=_env(step.env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=step.timeout,
            check=False,
        )
        output = _coerce(completed.stdout) + _coerce(completed.stderr)
        code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = _coerce(exc.stdout) + _coerce(exc.stderr)
        output += f"\n[verify] timed out after {step.timeout}s\n"
        code = 124
    except FileNotFoundError:
        output = f"[verify] command not found: {step.command[0]}\n"
        code = 127

    missing = [text for text in step.must_contain if text not in output]
    if code == 0 and missing:
        wanted = ", ".join(repr(text) for text in missing)
        output += f"\n[verify] missing expected output: {wanted}\n"
        code = 1

    seconds = time.perf_counter() - started
    log_path.write_text(f"$ {_display(command)}\n\n{output}", encoding="utf-8")
    passed = code == 0
    print(f"{'PASS' if passed else 'FAIL'}  {step.name:<24} {seconds:6.1f}s  {_rel(log_path)}")
    if not passed:
        print(f"      $ {_display(command)}")
        print(_tail(output))
    return Result(step.name, passed, seconds, f"exit {code}", log_path)


def _http_json(url: str, timeout: float = 5.0) -> tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, json.loads(body or "null")


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return cast(int, sock.getsockname()[1])


def _wait_for_server(server: subprocess.Popen[str], base_url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"explorer exited with code {server.returncode}")
        try:
            status, _ = _http_json(f"{base_url}/api/overview", timeout=1.0)
            if status == 200:
                return
        except (OSError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise RuntimeError(f"explorer did not become ready: {last_error}")


@contextmanager
def explorer_server(port: int, run_dir: Path) -> Iterator[tuple[str, Path]]:
    """Start the Explorer once and keep it alive for API and browser checks."""
    server_log = run_dir / "explorer-server.log"
    base = f"http://127.0.0.1:{port}"
    handle = server_log.open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-u", "-m", "explorer.server", "--port", str(port)],
        cwd=ROOT,
        env=_env({}),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(server, base)
        yield base, server_log
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        handle.close()


def check_explorer_api(base: str, server_log: Path, run_dir: Path) -> Result:
    name = "explorer API"
    evidence_path = run_dir / "explorer-api.json"
    started = time.perf_counter()
    try:
        summary: dict[str, Any] = {}

        status, overview = _http_json(f"{base}/api/overview")
        _expect(status == 200, f"/api/overview returned {status}")
        nodes = overview["nodes"]
        _expect(overview["event_count"] == len(nodes) > 0, "overview event count is inconsistent")
        _expect(
            overview["edge_count"] == len(overview["edges"]),
            "overview edge count is inconsistent",
        )
        _expect(bool(overview["failure_event_id"]), "demo trace has no failure target")
        summary["overview"] = {
            "status": status,
            "events": overview["event_count"],
            "edges": overview["edge_count"],
        }

        status, failure = _http_json(f"{base}/api/failure")
        _expect(status == 200, f"/api/failure returned {status}")
        _expect(
            failure["failure_event_id"] == overview["failure_event_id"],
            "failure endpoint disagrees with overview target",
        )
        summary["failure"] = {"status": status, "target": failure["failure_event_id"]}

        status, diagnosis = _http_json(f"{base}/api/diagnosis")
        _expect(status == 200, f"/api/diagnosis returned {status}")
        _expect(diagnosis["status"] == "ok", f"diagnosis status is {diagnosis['status']!r}")
        _expect(isinstance(diagnosis["dimensions"], dict), "diagnosis dimensions are missing")
        summary["diagnosis"] = {"status": status, "dimensions": len(diagnosis["dimensions"])}

        status, evidence = _http_json(f"{base}/api/evidence")
        _expect(status == 200, f"/api/evidence returned {status}")
        _expect(evidence["status"] == "ok", f"evidence status is {evidence['status']!r}")
        _expect(bool(evidence["summary"]), "evidence summary is empty")
        summary["evidence"] = {"status": status, "summary_chars": len(evidence["summary"])}

        failure_id = overview["failure_event_id"]
        status, detail = _http_json(f"{base}/api/event?id={failure_id}")
        _expect(status == 200, f"/api/event returned {status}")
        _expect(detail["id"] == failure_id, "event detail returned the wrong event")
        summary["event"] = {"status": status, "id": failure_id}

        status, _ = _http_json(f"{base}/api/event?id=missing-event")
        _expect(status == 404, f"unknown event returned {status}, expected 404")
        summary["unknown_event"] = {"status": status}

        with urllib.request.urlopen(f"{base}/", timeout=5) as response:
            html = response.read().decode("utf-8", errors="replace")
            _expect(response.status == 200, f"index returned {response.status}")
        _expect("DAG Explorer" in html, "served index does not contain the Explorer shell")
        summary["static_index"] = {"status": 200, "bytes": len(html)}

        evidence_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        seconds = time.perf_counter() - started
        counts = f"{overview['event_count']} events, {overview['edge_count']} edges"
        print(f"PASS  {name:<24} {seconds:6.1f}s  {counts}  {_rel(evidence_path)}")
        return Result(name, True, seconds, "6 endpoints + static index", evidence_path)
    except Exception as exc:  # noqa: BLE001 - verification reports any failure as evidence
        seconds = time.perf_counter() - started
        tail = _tail(server_log.read_text(encoding="utf-8", errors="replace"))
        print(f"FAIL  {name:<24} {seconds:6.1f}s  {_rel(server_log)}")
        print(f"      {exc}")
        if tail:
            print(tail)
        return Result(name, False, seconds, str(exc), server_log)


def check_playwright(port: int, run_dir: Path) -> Result:
    playwright_dir = run_dir / "playwright"
    step = Step(
        "explorer Playwright",
        (_tool("npx"), "playwright", "test"),
        cwd=FRONTEND,
        env={
            "EXPLORER_URL": f"http://127.0.0.1:{port}",
            "PLAYWRIGHT_OUTPUT_DIR": str(playwright_dir),
        },
        timeout=180,
        must_contain=("1 passed",),
    )
    result = run_step(step, run_dir)
    screenshots = sorted(playwright_dir.rglob("*.png")) if playwright_dir.is_dir() else []
    if result.passed and screenshots:
        print(f"      screenshot: {_rel(screenshots[0])}")
    return result


def static_steps(*, full: bool) -> list[Step]:
    npm = _tool("npm")
    steps = [
        Step("pytest", (_tool("uv"), "run", "pytest", "-q")),
        Step("ruff", (_tool("uv"), "run", "ruff", "check", ".")),
        Step("ty", (_tool("uv"), "run", "ty", "check", ".")),
        Step(
            "import boundaries",
            (sys.executable, "tools/verify/import_boundaries.py"),
            must_contain=("PASS import boundaries",),
        ),
        Step(
            "suppression budget",
            (sys.executable, "tools/verify/suppression_budget.py"),
            must_contain=("PASS suppression budget",),
        ),
        Step(
            "ingest receiver",
            (sys.executable, "tools/verify/ingest_smoke.py"),
            must_contain=("PASS ingest receiver",),
        ),
        Step(
            "plugin copy",
            (sys.executable, "scripts/sync-opencode-plugin.py", "--check"),
            must_contain=("plugin copy check passed",),
        ),
        Step("frontend tests", (npm, "test"), cwd=FRONTEND),
        Step("frontend typecheck", (_tool("npx"), "tsc", "--noEmit"), cwd=FRONTEND),
        Step("plugin build", (npm, "run", "build"), cwd=PLUGIN),
        Step("plugin tests", (npm, "test"), cwd=PLUGIN),
        Step("plugin typecheck", (npm, "run", "typecheck"), cwd=PLUGIN),
    ]
    if full:
        steps += [
            Step(
                "static sync",
                (sys.executable, "scripts/sync-explorer-static.py", "--check"),
                must_contain=("in sync",),
            ),
            Step("frontend build", (npm, "run", "build"), cwd=FRONTEND),
        ]
    return steps


def flow_steps() -> list[Step]:
    return [
        Step(
            "CLI fixture flow",
            (
                _tool("uv"),
                "run",
                "causality",
                "--fixture",
                "fixture/fixture.json",
                "agents",
            ),
            must_contain=("planner", "researcher", "coder"),
        ),
        Step(
            "example flow",
            (_tool("uv"), "run", "python", "examples/customer_approval.py"),
            must_contain=("Offline explanation", "Outcome: approved", "Failure event:"),
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    # Playwright prints Unicode marks; the Windows console defaults to cp1252.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = argparse.ArgumentParser(description="Verify Agent-Causality end to end")
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "skip frontend build, static sync, the Explorer server, and Playwright"
        ),
    )
    args = parser.parse_args(argv)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = ARTIFACTS / f"{stamp}-{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"verify: {'quick' if args.quick else 'full'} mode")
    print(f"artifacts: {_rel(run_dir)}")
    print()

    started = time.perf_counter()
    results = [run_step(step, run_dir) for step in static_steps(full=not args.quick)]
    results += [run_step(step, run_dir) for step in flow_steps()]

    if not args.quick:
        port = _free_port()
        try:
            with explorer_server(port, run_dir) as (base, server_log):
                results.append(check_explorer_api(base, server_log, run_dir))
                results.append(check_playwright(port, run_dir))
        except Exception as exc:  # noqa: BLE001 - verification reports any failure as evidence
            log = run_dir / "explorer-server.log"
            print(f"FAIL  {'explorer server':<24} {0.0:6.1f}s  {_rel(log)}")
            print(f"      {exc}")
            results.append(Result("explorer server", False, 0.0, str(exc), log))
    else:
        print("SKIP  explorer server + Playwright (quick mode)")

    total = time.perf_counter() - started
    failed = [result for result in results if not result.passed]
    print()
    print("=" * 72)
    print(f"{len(results) - len(failed)}/{len(results)} checks passed in {total:.1f}s")
    if failed:
        print("failed: " + ", ".join(result.name for result in failed))
        print(f"artifacts: {_rel(run_dir)}")
        return 1
    print(f"artifacts: {_rel(run_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
