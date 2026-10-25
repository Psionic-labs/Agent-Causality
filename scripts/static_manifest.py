"""Hash frontend build inputs so static-sync checks are path-independent.

Next.js embeds checkout-dependent module IDs in its chunks, so a build in a
linked worktree can differ byte-for-byte from the committed bundle even when
the source is identical. The manifest records the source inputs instead; the
sync script writes it and ``--check`` recomputes it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

INPUTS = (
    "frontend/app",
    "frontend/components",
    "frontend/lib",
    "frontend/public",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/next.config.ts",
    "frontend/tsconfig.json",
)
MANIFEST_NAME = ".frontend-inputs.json"
IGNORED = {"node_modules", ".next", "out", "__pycache__"}


def manifest_path(static_dir: Path) -> Path:
    return static_dir / MANIFEST_NAME


def _input_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in INPUTS:
        path = root / name
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
                and not any(part in IGNORED for part in candidate.relative_to(root).parts)
            )
    return _posix_sort(root, set(files))


def _normalized_bytes(path: Path) -> bytes:
    """Ignore CRLF/LF checkout differences; hash the content either way."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def input_hash(root: Path) -> str:
    """Hash relative paths and normalized bytes, never absolute checkout paths."""
    return _hash_files(root, _input_files(root))


def _static_files(static_dir: Path) -> list[Path]:
    files = [
        path
        for path in static_dir.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    ]
    return _posix_sort(static_dir, files)


def _posix_sort(root: Path, files: set[Path] | list[Path]) -> list[Path]:
    """Sort by case-sensitive relative POSIX path.

    ``Path`` ordering lowercases parts on Windows, so ``OFL.txt`` sorts after
    ``ibm-plex`` there and before it on Linux. The manifest hash has to match
    on both.
    """
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _hash_files(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in _posix_sort(root, files):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalized_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def static_hash(static_dir: Path) -> str:
    """Hash the vendored tree, excluding the manifest that records its hash."""
    return _hash_files(static_dir, _static_files(static_dir))


def write_manifest(root: Path, static_dir: Path) -> dict[str, object]:
    data: dict[str, object] = {
        "input_sha256": input_hash(root),
        "static_sha256": static_hash(static_dir),
        "files": [path.relative_to(root).as_posix() for path in _input_files(root)],
    }
    static_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(static_dir).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def read_manifest(static_dir: Path) -> dict[str, object] | None:
    path = manifest_path(static_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def check_manifest(root: Path, static_dir: Path) -> tuple[bool, str]:
    data = read_manifest(static_dir)
    if data is None:
        return False, "explorer/static/.frontend-inputs.json is missing; run sync"
    current = input_hash(root)
    if data.get("input_sha256") != current:
        return False, "frontend inputs changed since the last sync; rebuild and re-run sync"
    if data.get("static_sha256") != static_hash(static_dir):
        return False, "explorer/static files changed since the last sync; rebuild and re-run sync"
    return True, current
