"""Load a dotenv file at a process entry point."""

from __future__ import annotations

import os
from pathlib import Path


def _dotenv_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] in "\"'":
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
    comment_at = len(value)
    for index, char in enumerate(value):
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            comment_at = index
            break
    return value[:comment_at].rstrip()


def load_env_file(path: Path | None = None) -> None:
    """Set unset environment variables from a dotenv file.

    Missing files are ignored. Unreadable files raise ``OSError`` or
    ``UnicodeError``.
    """
    env_path = Path(".env") if path is None else path
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = _dotenv_value(val)
        if key and key not in os.environ:
            os.environ[key] = val
