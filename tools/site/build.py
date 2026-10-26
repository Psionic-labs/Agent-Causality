"""Render site chrome and the OpenCode, LangGraph, and case-study pages.

Home and paper keep their existing ``<main>``. This writer replaces the
header nav, the footer nav, and the menu boot markup, then writes the
guide pages from ``docs/*.md``.
"""

from __future__ import annotations

import html
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.site.catalog import (
    REPO,
    SITE,
    Asset,
    Catalog,
    ExternalNav,
    InternalNav,
    NavItem,
    Page,
    load,
    page_by_id,
    validate,
)

FONT = "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap"
HAND_KINDS = frozenset({"home", "paper"})
NAV_RE = re.compile(r'<nav class="site-nav"[^>]*>.*?</nav>', re.DOTALL)
FOOTER_NAV_RE = re.compile(
    r'<nav class="footer-nav" aria-label="Footer">.*?</nav>',
    re.DOTALL,
)
BLOCK_START = re.compile(r"^(```|\||#{1,6} |>|- |\d+\. )")
ORDERED_ITEM = re.compile(r"^(\d+)\. (.*)$")
TABLE_RULE = re.compile(r"^:?-{3,}:?$")


def depth(path: str) -> int:
    return path.count("/")


def prefix(path: str) -> str:
    return "../" * depth(path)


def rel_href(from_path: str, to_path: str, fragment: str | None) -> str:
    if from_path == to_path:
        return f"#{fragment}" if fragment else Path(to_path).name
    start = Path(from_path).parent.as_posix()
    href = to_path if start == "." else Path(os.path.relpath(to_path, start)).as_posix()
    if fragment:
        return f"{href}#{fragment}"
    return href


def href_from(catalog: Catalog, current: Page, item: NavItem) -> str:
    if isinstance(item, ExternalNav):
        return item.url
    target = page_by_id(catalog, item.target.page_id)
    return rel_href(current.path, target.path, item.target.fragment)


def brand_href(catalog: Catalog, current: Page) -> str:
    if current.kind == "home":
        return "#top"
    home = page_by_id(catalog, "home")
    return rel_href(current.path, home.path, None)


def is_current(catalog: Catalog, current: Page, item: NavItem) -> bool:
    if not isinstance(item, InternalNav) or item.target.fragment:
        return False
    target = page_by_id(catalog, item.target.page_id)
    if target.id == current.id:
        return True
    return target.kind == "hub" and current.kind in {"hub", "doc"}


def render_anchor(catalog: Catalog, current: Page, item: NavItem) -> str:
    href = html.escape(href_from(catalog, current, item), quote=True)
    attrs = ""
    if item.mark == "github":
        attrs += ' class="nav-github"'
    attrs += f' href="{href}"'
    if is_current(catalog, current, item):
        attrs += ' aria-current="page"'
    if isinstance(item, ExternalNav) and item.new_tab:
        attrs += ' target="_blank" rel="noopener"'
    label = html.escape(item.label)
    if isinstance(item, ExternalNav) and item.new_tab:
        label += ' <span aria-hidden="true">↗</span>'
    return f"<a{attrs}>{label}</a>"


def render_primary(catalog: Catalog, current: Page) -> str:
    links = "\n".join(
        f"        {render_anchor(catalog, current, item)}" for item in catalog.primary
    )
    return (
        '<nav class="site-nav" id="site-nav" aria-label="Primary">\n'
        f"{links}\n"
        "      </nav>"
    )


def render_footer_nav(catalog: Catalog, current: Page) -> str:
    links = "\n".join(
        f"        {render_anchor(catalog, current, item)}" for item in catalog.footer
    )
    return (
        '<nav class="footer-nav" aria-label="Footer">\n'
        f"{links}\n"
        "      </nav>"
    )


def _boot(path: str) -> str:
    return (
        "  <script>\n"
        '    document.documentElement.setAttribute("data-nav-script", "on");\n'
        "  </script>\n"
        f'  <script src="{prefix(path)}nav.js" defer></script>\n'
    )


def _button() -> str:
    return (
        '<button type="button" class="nav-toggle" aria-controls="site-nav" '
        'aria-expanded="false">\n'
        '        <span class="nav-toggle-bars" aria-hidden="true"></span>\n'
        '        <span class="nav-toggle-label">Menu</span>\n'
        "      </button>\n"
        "      "
    )


def apply_chrome(source: str, catalog: Catalog, page: Page) -> str:
    if page.kind not in HAND_KINDS:
        raise ValueError(page.id)
    updated = source.replace(
        '<html lang="en">',
        '<html lang="en" data-nav="closed">',
        1,
    )
    if "data-nav-script" not in updated:
        boot = _boot(page.path)
        app_tag = '<script src="app.js"'
        if app_tag in updated:
            updated = updated.replace(app_tag, boot + app_tag, 1)
        else:
            updated = updated.replace("</head>", boot + "</head>", 1)
    nav = render_primary(catalog, page)
    updated, count = NAV_RE.subn(nav, updated, count=1)
    if count != 1:
        raise RuntimeError(f"{page.path} is missing the primary nav")
    if 'class="nav-toggle"' not in updated:
        updated = updated.replace(
            '<nav class="site-nav" id="site-nav" aria-label="Primary">',
            _button() + '<nav class="site-nav" id="site-nav" aria-label="Primary">',
            1,
        )
    footer = render_footer_nav(catalog, page)
    updated, count = FOOTER_NAV_RE.subn(footer, updated, count=1)
    if count != 1:
        raise RuntimeError(f"{page.path} is missing the footer nav")
    return updated


def rewrite_href(catalog: Catalog, page: Page, href: str) -> str:
    if page.markdown is None:
        return href
    target = href.strip()
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return target
    resolved = (page.markdown.parent / target).resolve()
    for other in catalog.pages:
        if other.markdown is not None and other.markdown.resolve() == resolved:
            return rel_href(page.path, other.path, None)
    try:
        relative = resolved.relative_to(REPO)
    except ValueError:
        return target
    return "https://github.com/Psionic-labs/Agent-Causality/blob/main/" + relative.as_posix()


def image_src(page: Page, src: str) -> str:
    if page.markdown is None or src.startswith(("http://", "https://")):
        return src
    resolved = (page.markdown.parent / src).resolve()
    for asset in page.assets:
        if asset.src.resolve() == resolved:
            return rel_href(page.path, asset.dest, None)
    return src


def _linked(text: str, start: int) -> tuple[str, str, int] | None:
    if start >= len(text) or text[start] != "[":
        return None
    close = text.find("]", start + 1)
    if close == -1 or close + 1 >= len(text) or text[close + 1] != "(":
        return None
    end = text.find(")", close + 2)
    if end == -1:
        return None
    return text[start + 1 : close], text[close + 2 : end].strip(), end + 1


def render_inline(text: str, catalog: Catalog, page: Page) -> str:
    parts: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("`", index):
            end = text.find("`", index + 1)
            if end == -1:
                parts.append("`")
                index += 1
                continue
            parts.append(f"<code>{html.escape(text[index + 1 : end])}</code>")
            index = end + 1
            continue
        if text.startswith("![", index):
            linked = _linked(text, index + 1)
            if linked is not None:
                alt, src, index = linked
                safe_src = html.escape(image_src(page, src), quote=True)
                safe_alt = html.escape(alt, quote=True)
                parts.append(f'<img src="{safe_src}" alt="{safe_alt}">')
                continue
        if text.startswith("[", index):
            linked = _linked(text, index)
            if linked is not None:
                label, href, index = linked
                safe_href = html.escape(rewrite_href(catalog, page, href), quote=True)
                inner = render_inline(label, catalog, page)
                parts.append(f'<a href="{safe_href}">{inner}</a>')
                continue
        if text.startswith("**", index):
            end = text.find("**", index + 2)
            if end != -1:
                inner = render_inline(text[index + 2 : end], catalog, page)
                parts.append(f"<strong>{inner}</strong>")
                index = end + 2
                continue
        if text.startswith("_", index) and _emphasis_at(text, index, "_"):
            end = _emphasis_end(text, index, "_")
            if end is not None:
                inner = render_inline(text[index + 1 : end], catalog, page)
                parts.append(f"<em>{inner}</em>")
                index = end + 1
                continue
        if text.startswith("<http://", index) or text.startswith("<https://", index):
            end = text.find(">", index + 1)
            if end != -1 and " " not in text[index + 1 : end]:
                url = text[index + 1 : end]
                safe = html.escape(url, quote=True)
                parts.append(f'<a href="{safe}">{safe}</a>')
                index = end + 1
                continue
        if text.startswith("*", index) and not text.startswith("**", index):
            end = text.find("*", index + 1)
            if end != -1 and not text.startswith("**", end):
                inner = render_inline(text[index + 1 : end], catalog, page)
                parts.append(f"<em>{inner}</em>")
                index = end + 1
                continue
        parts.append(html.escape(text[index]))
        index += 1
    return "".join(parts)


def _emphasis_at(text: str, index: int, mark: str) -> bool:
    previous = text[index - 1] if index else ""
    return previous == "" or not (previous.isalnum() or previous == mark)


def _emphasis_end(text: str, index: int, mark: str) -> int | None:
    end = text.find(mark, index + 1)
    while end != -1:
        after = text[end + 1] if end + 1 < len(text) else ""
        if after == "" or not (after.isalnum() or after == mark):
            return end
        end = text.find(mark, end + 1)
    return None


def _starts_block(line: str) -> bool:
    return BLOCK_START.match(line) is not None


@dataclass(frozen=True)
class CodeBlock:
    text: str


@dataclass(frozen=True)
class TableBlock:
    rows: tuple[str, ...]


@dataclass(frozen=True)
class HeadingBlock:
    level: int
    text: str


@dataclass(frozen=True)
class TextBlock:
    kind: str
    text: str


@dataclass(frozen=True)
class ListBlock:
    kind: str
    items: tuple[str, ...]


Block = CodeBlock | TableBlock | HeadingBlock | TextBlock | ListBlock


def parse_blocks(lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            body: list[str] = []
            while index < total and not lines[index].startswith("```"):
                body.append(lines[index])
                index += 1
            if index < total:
                index += 1
            blocks.append(CodeBlock("\n".join(body)))
            continue
        if line.startswith("|"):
            rows: list[str] = []
            while index < total and lines[index].startswith("|"):
                rows.append(lines[index])
                index += 1
            blocks.append(TableBlock(tuple(rows)))
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            blocks.append(HeadingBlock(level, line[level:].strip()))
            index += 1
            continue
        if line.startswith(">"):
            quote: list[str] = []
            while index < total and lines[index].startswith(">"):
                quote.append(lines[index][1:].lstrip())
                index += 1
            blocks.append(TextBlock("quote", " ".join(quote)))
            continue
        ordered = ORDERED_ITEM.match(line)
        if ordered or line.startswith("- "):
            kind = "ol" if ordered else "ul"
            items: list[str] = []
            while index < total:
                current = lines[index]
                matched = ORDERED_ITEM.match(current) if kind == "ol" else None
                if kind == "ul" and current.startswith("- "):
                    chunk = [current[2:]]
                elif matched is not None:
                    chunk = [matched.group(2)]
                else:
                    break
                index += 1
                while index < total and lines[index][:1] in {" ", "\t"} and lines[index].strip():
                    chunk.append(lines[index].strip())
                    index += 1
                items.append(" ".join(chunk))
            blocks.append(ListBlock(kind, tuple(items)))
            continue
        paragraph = [line.strip()]
        index += 1
        while index < total and lines[index].strip() and not _starts_block(lines[index]):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(TextBlock("p", " ".join(paragraph)))
    return blocks


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _render_table(rows: tuple[str, ...], catalog: Catalog, page: Page) -> str:
    parsed = [_cells(row) for row in rows]
    head = parsed[0]
    body = [row for row in parsed[1:] if not all(TABLE_RULE.fullmatch(cell) for cell in row)]
    head_html = "".join(f"<th>{render_inline(cell, catalog, page)}</th>" for cell in head)
    body_rows = []
    for row in body:
        cells = "".join(f"<td>{render_inline(cell, catalog, page)}</td>" for cell in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<div class="doc-table-wrap"><table>'
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def render_blocks(blocks: list[Block], catalog: Catalog, page: Page) -> str:
    chunks: list[str] = []
    for block in blocks:
        if isinstance(block, CodeBlock):
            chunks.append(f"<pre><code>{html.escape(block.text)}</code></pre>")
        elif isinstance(block, TableBlock):
            chunks.append(_render_table(block.rows, catalog, page))
        elif isinstance(block, HeadingBlock):
            level = min(max(block.level, 2), 4)
            inner = render_inline(block.text, catalog, page)
            chunks.append(f"<h{level}>{inner}</h{level}>")
        elif isinstance(block, TextBlock) and block.kind == "quote":
            inner = render_inline(block.text, catalog, page)
            chunks.append(f"<blockquote><p>{inner}</p></blockquote>")
        elif isinstance(block, ListBlock):
            items = "".join(
                f"<li>{render_inline(item, catalog, page)}</li>" for item in block.items
            )
            chunks.append(f"<{block.kind}>{items}</{block.kind}>")
        elif isinstance(block, TextBlock):
            chunks.append(f"<p>{render_inline(block.text, catalog, page)}</p>")
        else:
            raise ValueError(f"unknown block {block}")
    return "\n".join(chunks)


def article_parts(catalog: Catalog, page: Page) -> tuple[str, str]:
    if page.markdown is None:
        raise ValueError(page.id)
    lines = page.markdown.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines) and lines[index].startswith("# "):
        index += 1
    blocks = parse_blocks(lines[index:])
    lede = ""
    if blocks and isinstance(blocks[0], TextBlock) and blocks[0].kind == "quote":
        lede = render_inline(blocks[0].text, catalog, page)
        blocks = blocks[1:]
    return lede, render_blocks(blocks, catalog, page)


def _guide_links(catalog: Catalog, current: Page) -> str:
    items: list[str] = []
    for page in catalog.pages:
        if not page.in_doc_nav:
            continue
        href = html.escape(rel_href(current.path, page.path, None), quote=True)
        current_attr = ' aria-current="page"' if page.id == current.id else ""
        items.append(
            f'            <li><a href="{href}"{current_attr}>{html.escape(page.label)}</a></li>'
        )
    return "\n".join(items)


def _hub_body(catalog: Catalog, current: Page) -> str:
    cards: list[str] = []
    for page in catalog.pages:
        if not page.in_doc_nav:
            continue
        href = html.escape(rel_href(current.path, page.path, None), quote=True)
        cards.append(
            "          <li>\n"
            f'            <a href="{href}">\n'
            f'              <span class="doc-index-title">{html.escape(page.title)}</span>\n'
            f'              <span class="doc-index-desc">{html.escape(page.description)}</span>\n'
            "            </a>\n"
            "          </li>"
        )
    return '<ul class="doc-index">\n' + "\n".join(cards) + "\n        </ul>"


def _favicon() -> str:
    text = (SITE / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<link rel="icon" href="([^"]+)">', text)
    if match is None:
        raise RuntimeError("index.html is missing the favicon")
    return match.group(1)


def render_header(catalog: Catalog, current: Page) -> str:
    href = html.escape(brand_href(catalog, current), quote=True)
    label = "back to top" if current.kind == "home" else "back to the home page"
    return (
        '  <a class="skip-link" href="#main">Skip to content</a>\n'
        '  <header class="site-header">\n'
        '    <div class="wrap header-inner">\n'
        f'      <a class="brand" href="{href}" aria-label="Agent-Causality, {label}">\n'
        '        <span class="brand-mark" aria-hidden="true"><i></i></span>\n'
        '        <span class="brand-name">AGENT-CAUSALITY</span>\n'
        "      </a>\n"
        f"      {_button()}"
        f"{render_primary(catalog, current)}\n"
        "    </div>\n"
        "  </header>"
    )


def render_footer(catalog: Catalog, current: Page) -> str:
    href = html.escape(brand_href(catalog, current), quote=True)
    label = "back to top" if current.kind == "home" else "back to the home page"
    return (
        '  <footer class="site-footer">\n'
        '    <div class="wrap footer-top">\n'
        '      <div class="footer-brand">\n'
        f'        <a class="brand" href="{href}" aria-label="Agent-Causality, {label}">\n'
        '          <span class="brand-mark" aria-hidden="true"><i></i></span>\n'
        '          <span class="brand-name">AGENT-CAUSALITY</span>\n'
        "        </a>\n"
        "        <p>Causal debugging for branching multi-agent systems.</p>\n"
        "      </div>\n"
        f"      {render_footer_nav(catalog, current)}\n"
        "    </div>\n"
        '    <div class="wrap footer-legal">\n'
        "      <p>Built by Psionics · © 2026 · Agent-Causality is open source under AGPL-3.0.</p>\n"
        '      <p class="footer-credit">Visual style inspired by the timeline monitors '
        "in the Loki series. Not affiliated with or endorsed by Marvel, Disney, "
        "or the creators of the show.</p>\n"
        "    </div>\n"
        "  </footer>"
    )


def render_page(catalog: Catalog, page: Page) -> str:
    if page.kind == "hub":
        lede = html.escape(page.description)
        body = _hub_body(catalog, page)
    else:
        lede, body = article_parts(catalog, page)
    lede_html = f'        <p class="section-lede">{lede}</p>\n' if lede else ""
    icon = html.escape(_favicon(), quote=False)
    root = prefix(page.path)
    title = html.escape(f"{page.title}, Agent-Causality")
    description = html.escape(page.description, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en" data-nav="closed">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{title}</title>\n"
        f'  <meta name="description" content="{description}">\n'
        '  <meta name="theme-color" content="#0e0905">\n'
        f'  <link rel="icon" href="{icon}">\n'
        f'  <link rel="stylesheet" href="{FONT}">\n'
        f'  <link rel="stylesheet" href="{root}style.css">\n'
        f"{_boot(page.path)}"
        "</head>\n"
        "<body>\n"
        f"{render_header(catalog, page)}\n"
        '\n'
        '  <main id="main" class="paper-page doc-page">\n'
        '    <div class="wrap">\n'
        '      <div class="paper-layout">\n'
        '        <nav class="paper-legend" aria-label="Guides">\n'
        "          <h2>Guides</h2>\n"
        "          <ol>\n"
        f"{_guide_links(catalog, page)}\n"
        "          </ol>\n"
        "        </nav>\n"
        '        <article class="doc-article">\n'
        f'          <h1 class="paper-title">{html.escape(page.title)}</h1>\n'
        f"{lede_html}"
        '          <div class="doc-body">\n'
        f"{body}\n"
        "          </div>\n"
        "        </article>\n"
        "      </div>\n"
        "    </div>\n"
        "  </main>\n"
        "\n"
        f"{render_footer(catalog, page)}\n"
        "</body>\n"
        "</html>\n"
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    if path.is_file() and path.read_bytes() == data:
        return
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _copy_asset(asset: Asset) -> None:
    destination = SITE / asset.dest
    data = asset.src.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.read_bytes() == data:
        return
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)


def _generated_paths(catalog: Catalog) -> set[str]:
    return {page.path for page in catalog.pages if page.kind in {"hub", "doc"}}


def _stray_html(catalog: Catalog) -> list[str]:
    expected = _generated_paths(catalog)
    stray: list[str] = []
    docs = SITE / "docs"
    if not docs.is_dir():
        return stray
    for path in docs.rglob("*.html"):
        relative = path.relative_to(SITE).as_posix()
        if relative not in expected:
            stray.append(relative)
    return sorted(stray)


def build(catalog: Catalog | None = None) -> None:
    catalog = load() if catalog is None else catalog
    validate(catalog)
    for page in catalog.pages:
        if page.kind in HAND_KINDS:
            path = SITE / page.path
            updated = apply_chrome(path.read_text(encoding="utf-8"), catalog, page)
            _write(path, updated)
            continue
        if page.kind in {"hub", "doc"}:
            _write(SITE / page.path, render_page(catalog, page))
            for asset in page.assets:
                _copy_asset(asset)
    for relative in _stray_html(catalog):
        (SITE / relative).unlink()


def check(catalog: Catalog | None = None) -> int:
    catalog = load() if catalog is None else catalog
    validate(catalog)
    stale: list[str] = []
    for page in catalog.pages:
        path = SITE / page.path
        if page.kind in HAND_KINDS:
            current = path.read_text(encoding="utf-8")
            if apply_chrome(current, catalog, page) != current:
                stale.append(page.path)
            continue
        expected = render_page(catalog, page)
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(page.path)
        for asset in page.assets:
            destination = SITE / asset.dest
            if not destination.is_file() or destination.read_bytes() != asset.src.read_bytes():
                stale.append(asset.dest)
    stale.extend(_stray_html(catalog))
    if stale:
        print("site docs are stale. Run: uv run python -m tools.site.build", file=sys.stderr)
        for item in stale:
            print(f"  {item}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--check"]:
        return check()
    if args:
        print("usage: python -m tools.site.build [--check]", file=sys.stderr)
        return 2
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
