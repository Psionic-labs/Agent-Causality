from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from scripts.static_manifest import check_manifest, input_hash, write_manifest
from tools.verify.verify import static_steps


def _make_tree(root: Path) -> None:
    (root / "frontend" / "app").mkdir(parents=True)
    (root / "frontend" / "app" / "page.tsx").write_text("export default 1\n", encoding="utf-8")
    (root / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")


def test_input_hash_is_path_independent(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _make_tree(first)
    _make_tree(second)

    assert input_hash(first) == input_hash(second)


def test_input_hash_ignores_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    _make_tree(lf)
    _make_tree(crlf)
    page = "export default 1\n"
    (crlf / "frontend" / "app" / "page.tsx").write_bytes(
        page.replace("\n", "\r\n").encode("utf-8")
    )

    assert input_hash(lf) == input_hash(crlf)


def test_changed_source_without_regeneration_fails(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _make_tree(root)
    static = root / "explorer" / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("ok\n", encoding="utf-8")
    write_manifest(root, static)

    assert check_manifest(root, static)[0] is True

    (root / "frontend" / "app" / "page.tsx").write_text("export default 2\n", encoding="utf-8")
    ok, message = check_manifest(root, static)

    assert ok is False
    assert "changed" in message


def test_changed_static_file_without_regeneration_fails(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _make_tree(root)
    static = root / "explorer" / "static"
    static.mkdir(parents=True)
    index = static / "index.html"
    index.write_text("ok\n", encoding="utf-8")
    write_manifest(root, static)

    index.write_text("hand edit\n", encoding="utf-8")
    ok, message = check_manifest(root, static)

    assert ok is False
    assert "explorer/static files changed" in message


def test_full_verify_checks_static_sync_before_frontend_build() -> None:
    names = [step.name for step in static_steps(full=True)]

    assert names.index("static sync") < names.index("frontend build")


def _load_sync() -> Any:
    script = Path("scripts/sync-explorer-static.py").resolve()
    scripts_dir = str(script.parent)
    # The script imports its sibling the same way `python scripts/sync-explorer-static.py` does.
    sys.path.insert(0, scripts_dir)
    try:
        spec = importlib.util.spec_from_file_location("sync_explorer_static_under_test", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load scripts/sync-explorer-static.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(scripts_dir)


def test_check_uses_manifest_when_frontend_out_is_missing(tmp_path: Path, capsys: Any) -> None:
    root = tmp_path / "repo"
    _make_tree(root)
    static = root / "explorer" / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("ok\n", encoding="utf-8")
    write_manifest(root, static)

    module = _load_sync()
    module.ROOT = root
    module.SRC = root / "frontend" / "out"
    module.DST = static

    assert not module.SRC.joinpath("index.html").is_file()
    assert module.check() == 0
    assert "in sync" in capsys.readouterr().out

    (root / "frontend" / "app" / "page.tsx").write_text("export default 2\n", encoding="utf-8")
    assert module.check() == 1
    err = capsys.readouterr().err
    assert "frontend inputs changed" in err
    assert "cannot check freshness" not in err
