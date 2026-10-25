from __future__ import annotations

from tools.verify.cleanup_inventory import table_suppressions

TABLE = """\
# Cleanup

| File | Line | Rule | Why |
|---|---:|---|---|
| `cli/main.py` | 233 | BLE001 | one line |

| File | Module imported | Why |
|---|---|---|
| `explorer/loader.py` | `benchmark.opencode.scoring` | layering |

| File | Line(s) | Rule |
|---|---:|---|
| `benchmark/opencode/scoring.py` | 375, 389, 440 | BLE001 |
| `storage/sqlite.py` | 99, 161 | SIM117 |
"""


def test_counts_line_lists_and_module_rows() -> None:
    # 1 + 1 + 3 + 2
    assert table_suppressions(TABLE) == 7


def test_ignores_headers_and_separators() -> None:
    assert table_suppressions(TABLE) == table_suppressions(TABLE.replace("# Cleanup\n", ""))


def test_empty_text_has_no_suppressions() -> None:
    assert table_suppressions("") == 0
