"""Sync the canonical OpenCode plugin source into the local OpenCode install.

Source: ``packages/opencode-agent-causality/src/index.ts``
Destination: ``.opencode/plugins/agent-causality.ts`` (gitignored install copy)

Usage:
    uv run python scripts/sync-opencode-plugin.py
    uv run python scripts/sync-opencode-plugin.py --check   # fail if stale
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "packages" / "opencode-agent-causality" / "src" / "index.ts"
DST = ROOT / ".opencode" / "plugins" / "agent-causality.ts"


def _fail(message: str) -> int:
    print(f"sync-opencode-plugin: {message}", file=sys.stderr)
    return 1


def sync() -> int:
    if not SRC.is_file():
        return _fail(f"canonical plugin source is missing: {SRC.relative_to(ROOT)}")
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, DST)
    print(f"synced {SRC.relative_to(ROOT)} -> {DST.relative_to(ROOT)}")
    return 0


def check() -> int:
    if not SRC.is_file():
        return _fail(f"canonical plugin source is missing: {SRC.relative_to(ROOT)}")
    if not DST.is_file():
        print("plugin copy check passed: not installed (skipped)")
        return 0
    if DST.read_bytes() != SRC.read_bytes():
        return _fail(
            f"{DST.relative_to(ROOT)} is stale; re-run "
            "`uv run python scripts/sync-opencode-plugin.py`"
        )
    print(f"plugin copy check passed: {DST.relative_to(ROOT)} is in sync")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync the local OpenCode plugin copy")
    parser.add_argument("--check", action="store_true", help="fail if the installed copy is stale")
    args = parser.parse_args(argv)
    return check() if args.check else sync()


if __name__ == "__main__":
    raise SystemExit(main())
