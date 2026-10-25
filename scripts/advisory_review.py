"""Choose the advisory review credential and the model it authenticates.

``opencode run --model`` is the reviewer. Each row is an environment variable
this repository already uses for that command, paired with the model id that
variable authenticates. The first variable with a non-empty value wins.
No match skips the review.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping

# Preference order. An OpenCode key keeps the model the workflow already used.
REVIEW_CREDENTIALS: tuple[tuple[str, str], ...] = (
    ("OPENCODE_API_KEY", "opencode/deepseek-v4.1-flash-free"),
    ("OPENROUTER_API_KEY", "openrouter/deepseek/deepseek-v4-flash"),
)


def select_review_credential(env: Mapping[str, str]) -> tuple[str, str] | None:
    for name, model in REVIEW_CREDENTIALS:
        if env.get(name, "").strip():
            return name, model
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select an advisory review credential")
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="append enabled= and model= lines for GitHub Actions",
    )
    args = parser.parse_args(argv)
    chosen = select_review_credential(os.environ)
    if chosen is None:
        names = ", ".join(name for name, _model in REVIEW_CREDENTIALS)
        print(
            f"No advisory review credential is set ({names}); skipping the advisory review.",
            file=sys.stderr,
        )
        lines = ["enabled=false"]
    else:
        name, model = chosen
        print(f"advisory review credential: {name}")
        print(f"advisory review model: {model}")
        lines = ["enabled=true", f"model={model}", f"credential={name}"]
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
