/**
 * Theme Store
 *
 * Manages dark/light mode theme preference with localStorage persistence.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "dark" | "light" | "system";

interface ThemeState {
  mode: ThemeMode;
  resolvedTheme: "dark" | "light";
  setMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}

// Get system preference
const getSystemTheme = (): "dark" | "light" => {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

// Resolve theme based on mode
const resolveTheme = (mode: ThemeMode): "dark" | "light" => {
  if (mode === "system") {
    return getSystemTheme();
  }
  return mode;
};

// Apply theme to document
const applyTheme = (theme: "dark" | "light") => {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.classList.remove("theme-dark", "theme-light");
  document.documentElement.classList.add(`theme-${theme}`);
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: "dark",
      resolvedTheme: "dark",

      setMode: (mode: ThemeMode) => {
        const resolvedTheme = resolveTheme(mode);
        applyTheme(resolvedTheme);
        set({ mode, resolvedTheme });
      },

      toggleTheme: () => {
        const currentMode = get().mode;
        const newMode: ThemeMode =
          currentMode === "dark"
            ? "light"
            : currentMode === "light"
              ? "dark"
              : getSystemTheme() === "dark"
                ? "light"
                : "dark";
        get().setMode(newMode);
      },
    }),
    {
      name: "claude-agent-theme",
      onRehydrateStorage: () => (state) => {
        if (state) {
          const resolved = resolveTheme(state.mode);
          applyTheme(resolved);
          state.resolvedTheme = resolved;
        }
      },
    }
  )
);

// Listen for system theme changes
if (typeof window !== "undefined") {
  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
  mediaQuery.addEventListener("change", () => {
    const state = useThemeStore.getState();
    if (state.mode === "system") {
      const resolved = resolveTheme("system");
      applyTheme(resolved);
      useThemeStore.setState({ resolvedTheme: resolved });
    }
  });

  // Apply initial theme
  const initialState = useThemeStore.getState();
  applyTheme(resolveTheme(initialState.mode));
}
