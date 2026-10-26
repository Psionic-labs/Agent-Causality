from __future__ import annotations

from tools.site.build import apply_chrome, article_parts, check
from tools.site.catalog import SITE, load, page_by_id


def _main(text: str) -> str:
    start = text.index("<main")
    end = text.index("</main>") + len("</main>")
    return text[start:end]


def test_opencode_guide_keeps_the_ingest_table_and_repo_links() -> None:
    catalog = load()
    page = page_by_id(catalog, "opencode")
    lede, body = article_parts(catalog, page)

    assert "both" in lede
    assert "<strong>" in lede
    assert "<table>" in body
    assert "CAUSALITY_OPENCODE_INGEST_URL" in body
    assert "<em>(unset)</em>" in body
    assert "<pre><code>" in body
    assert "causality-opencode-ingest" in body
    assert "&lt;path&gt;" in body
    assert "blob/main/packages/opencode-agent-causality/src/index.ts" in body
    assert 'href="http://127.0.0.1:8797"' in body
    assert "<h1>" not in body


def test_langgraph_guide_links_to_the_case_study_and_keeps_snake_case() -> None:
    catalog = load()
    page = page_by_id(catalog, "langgraph")
    _lede, body = article_parts(catalog, page)

    assert 'href="case-study-replit.html"' in body
    assert "blob/main/examples/replit_incident.py" in body
    assert "blob/main/adapters/langgraph/mapping.py" in body
    assert "parent_run_id" in body
    assert "<em>run</em>" not in body


def test_case_study_image_stays_on_the_site() -> None:
    catalog = load()
    page = page_by_id(catalog, "case-study-replit")
    _lede, body = article_parts(catalog, page)

    assert 'src="screenshots/replit_example.png"' in body
    assert 'href="langgraph.html"' in body


def test_home_chrome_is_idempotent_and_keeps_the_page_body() -> None:
    catalog = load()
    home = page_by_id(catalog, "home")
    source = (SITE / "index.html").read_text(encoding="utf-8")
    once = apply_chrome(source, catalog, home)
    twice = apply_chrome(once, catalog, home)

    assert once == twice
    assert _main(source) == _main(once)
    assert 'href="#problem"' in once
    assert 'href="docs/index.html"' in once
    assert 'class="nav-toggle"' in once
    assert "nav-more" not in once
    assert 'data-nav="closed"' in once


def test_paper_section_links_return_to_the_home_page() -> None:
    catalog = load()
    paper = page_by_id(catalog, "paper")
    source = (SITE / "paper.html").read_text(encoding="utf-8")
    updated = apply_chrome(source, catalog, paper)

    assert 'href="index.html#problem"' in updated
    assert 'href="docs/index.html"' in updated
    assert updated.count("app.js") == source.count("app.js")
    assert 'aria-current="page"' in updated


def test_committed_site_matches_the_builder() -> None:
    assert check() == 0
