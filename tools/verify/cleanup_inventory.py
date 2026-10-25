"""Parse the suppression inventory from CLEANUP.md.

The total is derived from the table rows so it cannot drift from the code.
Each data row's second cell is either a comma-separated list of lines (one
suppression per line) or a module name (one import-boundary suppression).
"""

from __future__ import annotations

import re

TABLE_ROW_RE = re.compile(r"^\|\s*`(?P<path>[^`]+)`\s*\|(?P<cells>[^|]*)\|")
LINE_LIST_RE = re.compile(r"^\s*\d+(?:\s*,\s*\d+)*\s*$")


def table_suppressions(text: str) -> int:
    total = 0
    for line in text.splitlines():
        match = TABLE_ROW_RE.match(line)
        if match is None:
            continue
        cells = match.group("cells").strip()
        if LINE_LIST_RE.fullmatch(cells):
            total += len(cells.split(","))
        else:
            total += 1
    return total
