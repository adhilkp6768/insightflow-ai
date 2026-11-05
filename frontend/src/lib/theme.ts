export type Theme = "light" | "dark"

const STORAGE_KEY = "insightflow-theme"

export function getStoredTheme(): Theme {
  return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light"
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark")
  localStorage.setItem(STORAGE_KEY, theme)
}

export function applyStoredTheme() {
  applyTheme(getStoredTheme())
}
