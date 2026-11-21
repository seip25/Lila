import { useCallback, useEffect, useState } from "react";
import { cn } from "./cn";

type Theme = "light" | "dark";
const KEY = "lila-theme"; // same key as lila-client.js: Jinja and React pages share the choice

function current(): Theme {
  const html = document.documentElement;
  return html.getAttribute("data-theme") === "dark" || html.classList.contains("dark") ? "dark" : "light";
}

function apply(theme: Theme) {
  const html = document.documentElement;
  html.setAttribute("data-theme", theme);
  html.classList.toggle("dark", theme === "dark");
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => (typeof document === "undefined" ? "light" : current()));
  const setTheme = useCallback((next: Theme) => {
    apply(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {}
    setThemeState(next);
  }, []);
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeState(current()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    return () => observer.disconnect();
  }, []);
  return { theme, isDark: theme === "dark", setTheme, toggleTheme: () => setTheme(theme === "dark" ? "light" : "dark") };
}

export function ThemeToggle({ className }: { className?: string }) {
  const { isDark, toggleTheme } = useTheme();
  return (
    <button type="button" onClick={toggleTheme} className={cn("btn-ghost btn-icon", className)} aria-label={isDark ? "Light mode" : "Dark mode"} title={isDark ? "Light mode" : "Dark mode"}>
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}
