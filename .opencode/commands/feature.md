---
description: Build a feature from its data shape and verify it end to end
---
Feature: $ARGUMENTS

1. Start by naming the data shape: types, fields, invariants, and who owns each value.
   Do not write code before this is explicit.
2. Follow the blessed pattern for the task in AGENTS.md.
3. Add focused tests for the behavior.
4. Run `uv run python tools/verify/verify.py --quick` after each edit.
5. Before finishing, run the full `uv run python tools/verify/verify.py`.
6. Report the PASS/FAIL summary and artifact paths.
7. No new suppressions without a CLEANUP.md row.
