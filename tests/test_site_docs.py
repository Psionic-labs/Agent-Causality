from __future__ import annotations

from tools.site.build import apply_chrome, check
from tools.site.catalog import SITE, load, page_by_id


def _main(text: str) -> str:
    start = text.index("<main")
    end = text.index("</main>") + len("</main>")
    return text[start:end]


def test_home_chrome_is_idempotent_and_keeps_the_page_body() -> None:
    catalog = load()
    home = page_by_id(catalog, "home")
    source = (SITE / "index.html").read_text(encoding="utf-8")
    once = apply_chrome(source, catalog, home)
    twice = apply_chrome(once, catalog, home)

    assert once == twice
    assert _main(source) == _main(once)
    assert 'href="#incidents"' in once
    assert 'href="proof.html"' in once
    assert 'href="opencode.html"' in once
    assert 'href="paper.html"' in once
    assert 'class="nav-github"' in once
    assert 'aria-label="GitHub"' in once
    assert "nav-toggle" not in once
    assert "nav.js" not in once
    assert "AGPL-3.0 license" not in once


def test_paper_section_links_return_to_the_home_page() -> None:
    catalog = load()
    paper = page_by_id(catalog, "paper")
    source = (SITE / "paper.html").read_text(encoding="utf-8")
    updated = apply_chrome(source, catalog, paper)

    assert 'href="index.html#incidents"' in updated
    assert 'href="opencode.html"' in updated
    assert updated.count("app.js") == source.count("app.js")
    assert 'aria-current="page"' in updated


def test_paper_page_exposes_scholar_citation() -> None:
    catalog = load()
    paper = page_by_id(catalog, "paper")
    source = (SITE / "paper.html").read_text(encoding="utf-8")
    updated = apply_chrome(source, catalog, paper)
    title = (
        "Agent-Causality: Declared Dependency Tracing and "
        "Counterfactual Sensitivity Analysis for Multi-Agent Systems"
    )
    pdf = "https://psionic-labs.github.io/Agent-Causality/agentic_causality_paper.pdf"
    for page in (source, updated):
        assert f'name="citation_title" content="{title}"' in page
        assert 'name="citation_author" content="Vasant Kumar Mogia"' in page
        assert 'name="citation_publication_date" content="2026/10/28"' in page
        assert f'name="citation_pdf_url" content="{pdf}"' in page
        assert "AI systems built from several cooperating agents are easy to record" in page
        assert 'href="agentic_causality_paper.pdf"' in page


def test_guides_stay_short() -> None:
    opencode = (SITE / "opencode.html").read_text(encoding="utf-8")
    langgraph = (SITE / "langgraph.html").read_text(encoding="utf-8")

    assert "causality-opencode-ingest" in opencode
    assert "CausalityCallbackHandler" in langgraph
    assert "adapters/langgraph/mapping.py" not in langgraph
    assert "case-study-replit" not in langgraph
    assert "packages/opencode-agent-causality/src/index.ts" not in opencode


def test_committed_site_matches_the_builder() -> None:
    assert check() == 0
