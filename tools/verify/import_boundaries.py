"""Check first-party import boundaries and the psycopg guard.

Rules are intentionally explicit. Existing violations live in
``import_boundaries_baseline.json`` and are listed in CLEANUP.md; anything new
fails here.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).with_name("import_boundaries_baseline.json")
PSYCOPG_GUARD = "storage/_psycopg.py"

FIRST_PARTY = {"sdk", "core", "storage", "adapters", "benchmark", "explorer", "cli", "causality"}

# A package may import itself plus the packages listed here. The graph is
# deliberately one-way: sdk <- core <- storage/adapters <- benchmark/explorer.
ALLOWED = {
    "sdk": {"sdk"},
    "core": {"core", "sdk"},
    "storage": {"storage", "core", "sdk"},
    "adapters": {"adapters", "storage", "core", "sdk"},
    "benchmark": {"benchmark", "adapters", "storage", "core", "sdk"},
    "explorer": {"explorer", "adapters", "storage", "core", "sdk"},
    "cli": {"cli", "explorer", "benchmark", "adapters", "storage", "core", "sdk"},
    "causality": {"causality", "storage", "core", "sdk"},
}

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    ".agents",
    ".opencode",
    ".causality",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".taste-skill",
    ".uv-cache",
    "agent_causality.egg-info",
    "brag-output",
    "dist",
    "explorer/static",
    "frontend",
    "node_modules",
    "paper",
    "test_pics",
    "tools/verify/artifacts",
}


@dataclass(frozen=True)
class ImportRef:
    path: str
    line: int
    module: str


def _files() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == part or rel.startswith(part + "/") for part in EXCLUDED_PARTS):
            continue
        found.append((path, rel))
    return sorted(found, key=lambda item: item[1])


def _imports(path: Path, rel: str) -> list[ImportRef]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except SyntaxError as exc:
        raise RuntimeError(f"cannot parse {rel}: {exc}") from exc

    refs: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.extend(ImportRef(rel, node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            refs.append(ImportRef(rel, node.lineno, node.module))
    return refs


def _load_baseline() -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    boundaries = {(entry["path"], entry["module"]) for entry in data["import_boundaries"]}
    psycopg = {(entry["path"], entry["module"]) for entry in data["psycopg"]}
    return boundaries, psycopg


def _check_boundaries(refs: list[ImportRef], baseline: set[tuple[str, str]]) -> list[str]:
    failures: list[str] = []
    for ref in refs:
        package = ref.path.split("/", 1)[0]
        allowed = ALLOWED.get(package)
        if allowed is None:
            continue
        imported = ref.module.split(".", 1)[0]
        if imported not in FIRST_PARTY or imported in allowed:
            continue
        if (ref.path, ref.module) in baseline:
            continue
        failures.append(
            f"{ref.path}:{ref.line} imports {ref.module}; "
            f"{package} may not import {imported}"
        )
    return failures


def _check_psycopg(refs: list[ImportRef], baseline: set[tuple[str, str]]) -> list[str]:
    failures: list[str] = []
    for ref in refs:
        if ref.path == PSYCOPG_GUARD:
            continue
        imported = ref.module.split(".", 1)[0]
        if imported != "psycopg":
            continue
        if (ref.path, "psycopg") in baseline:
            continue
        failures.append(
            f"{ref.path}:{ref.line} imports {ref.module}; "
            f"use storage._psycopg.load_psycopg/load_jsonb"
        )
    return failures


def main() -> int:
    baseline_boundaries, baseline_psycopg = _load_baseline()
    refs = [ref for path, rel in _files() for ref in _imports(path, rel)]
    failures = _check_boundaries(refs, baseline_boundaries)
    failures += _check_psycopg(refs, baseline_psycopg)
    baselined = len(baseline_boundaries) + len(baseline_psycopg)

    if failures:
        print(f"FAIL import boundaries ({len(failures)} unbaselined, {baselined} baselined)")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"PASS import boundaries ({baselined} baselined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
