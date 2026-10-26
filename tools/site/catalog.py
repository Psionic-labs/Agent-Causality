"""Nav and doc pages for the static site. This module is the only list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "agent-causality-site"
BLOB_BASE = "https://github.com/Psionic-labs/Agent-Causality/blob/main/"
GITHUB_REPO = "https://github.com/Psionic-labs/Agent-Causality"
LICENSE_BLOB = BLOB_BASE + "LICENSE"

Kind = Literal["home", "paper", "doc", "hub"]


@dataclass(frozen=True)
class Target:
    page_id: str
    fragment: str | None = None


@dataclass(frozen=True)
class Asset:
    src: Path
    dest: str


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    description: str
    path: str
    kind: Kind
    nav_label: str = ""
    markdown: Path | None = None
    assets: tuple[Asset, ...] = ()
    in_doc_nav: bool = False

    @property
    def label(self) -> str:
        return self.nav_label or self.title


@dataclass(frozen=True)
class InternalNav:
    id: str
    label: str
    target: Target
    mark: str | None = None


@dataclass(frozen=True)
class ExternalNav:
    id: str
    label: str
    url: str
    mark: str | None = None
    new_tab: bool = True


NavItem = InternalNav | ExternalNav


@dataclass(frozen=True)
class Catalog:
    pages: tuple[Page, ...]
    primary: tuple[NavItem, ...]
    footer: tuple[NavItem, ...]


def _pages() -> tuple[Page, ...]:
    docs = REPO / "docs"
    return (
        Page(
            "home",
            "Agent-Causality",
            "Causal debugging for multi-agent AI systems.",
            "index.html",
            "home",
        ),
        Page(
            "paper",
            "Research paper",
            "Declared dependency tracing and counterfactual sensitivity analysis.",
            "paper.html",
            "paper",
        ),
        Page(
            "docs",
            "Documentation",
            "Setup guides for OpenCode and LangGraph, plus the Replit case study.",
            "docs/index.html",
            "hub",
        ),
        Page(
            "opencode",
            "OpenCode integration",
            "Capture a live OpenCode session with the PyPI receiver and the npm plugin.",
            "docs/opencode.html",
            "doc",
            nav_label="OpenCode",
            markdown=docs / "opencode.md",
            in_doc_nav=True,
        ),
        Page(
            "langgraph",
            "LangGraph integration",
            "Record a LangGraph run with CausalityCallbackHandler and trace the causal edges.",
            "docs/langgraph.html",
            "doc",
            nav_label="LangGraph",
            markdown=docs / "langgraph.md",
            in_doc_nav=True,
        ),
        Page(
            "case-study-replit",
            "Case study: the Replit agent incident as a causal graph",
            "A documented agent failure replayed as a 22-event causal graph.",
            "docs/case-study-replit.html",
            "doc",
            nav_label="Replit case study",
            markdown=docs / "case-study-replit.md",
            assets=(
                Asset(
                    docs / "screenshots" / "replit_example.png",
                    "docs/screenshots/replit_example.png",
                ),
            ),
            in_doc_nav=True,
        ),
    )


def load() -> Catalog:
    pages = _pages()
    primary: tuple[NavItem, ...] = (
        InternalNav("problem", "Problem", Target("home", "problem")),
        InternalNav("solution", "Solution", Target("home", "solution")),
        InternalNav("how", "How it works", Target("home", "how")),
        InternalNav("trace", "Trace a run", Target("home", "trace")),
        InternalNav("quickstart", "Quickstart", Target("home", "quickstart")),
        InternalNav("docs", "Docs", Target("docs")),
        InternalNav("paper", "Paper", Target("paper")),
        ExternalNav("github", "GitHub", GITHUB_REPO, mark="github"),
    )
    footer: tuple[NavItem, ...] = (
        InternalNav("footer-paper", "Research paper", Target("paper")),
        ExternalNav("footer-github", "GitHub", GITHUB_REPO),
        InternalNav("footer-docs", "Documentation", Target("docs")),
        ExternalNav("footer-license", "AGPL-3.0 license", LICENSE_BLOB),
    )
    return Catalog(pages, primary, footer)


def validate(catalog: Catalog) -> None:
    ids = [page.id for page in catalog.pages]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate page id")
    by_id = {page.id: page for page in catalog.pages}
    for page in catalog.pages:
        if page.kind == "doc" and page.markdown is None:
            raise ValueError(f"{page.id} needs markdown")
        if page.kind != "doc" and page.markdown is not None:
            raise ValueError(f"{page.id} is not a markdown page")
        if page.kind == "doc" and not page.in_doc_nav:
            raise ValueError(f"{page.id} is missing from the guide list")
    for item in (*catalog.primary, *catalog.footer):
        if isinstance(item, InternalNav) and item.target.page_id not in by_id:
            raise ValueError(f"unknown target {item.target.page_id}")


def page_by_id(catalog: Catalog, page_id: str) -> Page:
    for page in catalog.pages:
        if page.id == page_id:
            return page
    raise KeyError(page_id)
