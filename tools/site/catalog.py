"""Nav and doc pages for the static site. This module is the only list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "agent-causality-site"
GITHUB_REPO = "https://github.com/Psionic-labs/Agent-Causality"

Kind = Literal["home", "paper", "proof", "guide", "doc", "hub"]


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
            "proof",
            "Proof",
            "Five live OpenCode runs. Capture coverage was complete. Naming the cause was not.",
            "proof.html",
            "proof",
        ),
        Page(
            "opencode",
            "OpenCode integration",
            "Live OpenCode capture needs agent-causality and the OpenCode plugin.",
            "opencode.html",
            "guide",
            nav_label="OpenCode",
        ),
        Page(
            "langgraph",
            "LangGraph integration",
            "Point a LangGraph run at CausalityCallbackHandler and read the causal graph.",
            "langgraph.html",
            "guide",
            nav_label="LangGraph",
        ),
    )


def load() -> Catalog:
    pages = _pages()
    primary: tuple[NavItem, ...] = (
        InternalNav("incidents", "Incidents", Target("home", "incidents")),
        InternalNav("how", "How it works", Target("home", "how")),
        InternalNav("trace", "Trace a run", Target("home", "trace")),
        InternalNav("proof", "Proof", Target("proof")),
        InternalNav("quickstart", "Quickstart", Target("home", "quickstart")),
        InternalNav("docs", "Docs", Target("opencode")),
        ExternalNav("github", "GitHub", GITHUB_REPO, mark="github"),
    )
    footer: tuple[NavItem, ...] = (
        InternalNav("footer-paper", "Research paper", Target("paper")),
        ExternalNav("footer-github", "GitHub", GITHUB_REPO),
        InternalNav("footer-docs", "Docs", Target("opencode")),
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
