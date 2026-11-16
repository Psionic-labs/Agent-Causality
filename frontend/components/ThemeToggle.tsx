"use client";

import { useEffect, useState } from "react";

type Theme = "night" | "daylight";

const STORAGE_KEY = "explorer-theme";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("night");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const next: Theme = saved === "daylight" ? "daylight" : "night";
    setTheme(next);
    applyTheme(next);
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    applyTheme(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }

  return (
    <div className="view-toggle" role="group" aria-label="Color theme">
      <button
        type="button"
        aria-pressed={theme === "night"}
        onClick={() => choose("night")}
      >
        Night desk
      </button>
      <button
        type="button"
        aria-pressed={theme === "daylight"}
        onClick={() => choose("daylight")}
      >
        Daylight
      </button>
    </div>
  );
}
