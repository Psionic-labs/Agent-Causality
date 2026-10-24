---
description: Review a diff against the repo rules and verify it
---
Review: $ARGUMENTS

1. Read the diff and check layering, generated files, suppressions, and tests.
2. Run `uv run python tools/verify/verify.py --quick` while reviewing.
3. Before finishing, run the full `uv run python tools/verify/verify.py`.
4. Report findings by severity plus the PASS/FAIL summary and artifact paths.
5. Call out any new suppression without a CLEANUP.md row.
