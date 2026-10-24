"""Fail when the suppression baseline grows beyond CLEANUP.md's stated total.

A suppression is a ``# noqa`` for one of the rules enabled during static
enforcement, a bare ``# type: ignore`` (PGH003), or an entry in the import
boundary baseline. The budget is the number in CLEANUP.md; adding a new
suppression requires adding a row there first.
"""

from __future__ import annotations

import io
import json
import re
import tokenize
from pathlib import Path

from import_boundaries import EXCLUDED_PARTS

ROOT = Path(__file__).resolve().parents[2]
CLEANUP = ROOT / "CLEANUP.md"
IMPORT_BASELINE = Path(__file__).with_name("import_boundaries_baseline.json")

BASELINE_RULES = {
    "BLE001",
    "SIM102",
    "SIM114",
    "SIM105",
    "SIM103",
    "SIM118",
    "SIM108",
    "SIM117",
    "SIM300",
    "PGH003",
}
NOQA_RE = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9, ]+))?")
TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore(?:\[(?P<codes>[^\]]+)\])?")
BUDGET_RE = re.compile(r"\*\*Total:\*\*\s*(\d+)\s+baselined", re.IGNORECASE)


def _budget() -> int:
    match = BUDGET_RE.search(CLEANUP.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError(f"cannot find '**Total:** N baselined' in {CLEANUP.name}")
    return int(match.group(1))


def _ruff_suppressions() -> int:
    count = 0
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == part or rel.startswith(part + "/") for part in EXCLUDED_PARTS):
            continue
        text = path.read_text(encoding="utf-8")
        suppressed_lines: set[int] = set()
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue
            comment = token.string
            noqa = NOQA_RE.search(comment)
            noqa_codes = set()
            if noqa is not None:
                raw = noqa.group("codes")
                noqa_codes = {code.strip() for code in raw.split(",")} if raw else set()
            noqa_hit = noqa is not None and (not noqa_codes or bool(noqa_codes & BASELINE_RULES))
            type_ignore = TYPE_IGNORE_RE.search(comment)
            type_hit = type_ignore is not None and not type_ignore.group("codes")
            if noqa_hit or type_hit:
                suppressed_lines.add(token.start[0])
        count += len(suppressed_lines)
    return count


def _import_suppressions() -> int:
    data = json.loads(IMPORT_BASELINE.read_text(encoding="utf-8"))
    return sum(len(entries) for entries in data.values())


def main() -> int:
    budget = _budget()
    ruff_count = _ruff_suppressions()
    import_count = _import_suppressions()
    total = ruff_count + import_count
    if total > budget:
        print(f"FAIL suppression budget: {total} > {budget} baselined suppressions")
        print("add a row to CLEANUP.md or fix the code")
        return 1
    print(
        f"PASS suppression budget ({total}/{budget} baselined; "
        f"ruff={ruff_count}, import_boundaries={import_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
