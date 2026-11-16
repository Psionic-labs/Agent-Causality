"use client";

import type { GraphOverview } from "../lib/types.ts";
import { ThemeToggle } from "./ThemeToggle.tsx";

export function Header({ overview }: { overview: GraphOverview }) {
  return (
    <header className="topbar">
      <div className="brand">
        <h1>DAG Explorer</h1>
        <span id="dataset-line" className="muted">
          {overview.source} · {overview.event_count} events · {overview.edge_count} causal edges
        </span>
      </div>
      <div className="header-readout">
        <ThemeToggle />
      </div>
    </header>
  );
}
