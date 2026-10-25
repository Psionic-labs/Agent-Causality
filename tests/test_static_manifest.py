from __future__ import annotations

from pathlib import Path

from scripts.static_manifest import check_manifest, input_hash, write_manifest


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
