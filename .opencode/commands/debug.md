---
description: Reproduce a bug, fix its root cause, and verify the result
---
Debug: $ARGUMENTS

1. Reproduce the bug with a failing test or a direct command. Quote the evidence.
2. Trace it to the first place the system goes wrong; fix the root cause, not the symptom.
3. Add a regression test that fails before the fix.
4. Run `uv run python tools/verify/verify.py --quick` after each edit.
5. Before finishing, run the full `uv run python tools/verify/verify.py`.
6. Report the PASS/FAIL summary, failing evidence, and artifact paths.
7. If you add a suppression, add a row to CLEANUP.md first.
