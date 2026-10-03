export type Theme = 'light' | 'dark'
const storageKey = 'economic-dashboard-theme'

export function initialTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(storageKey)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* Theme selection still works when browser storage is unavailable. */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function saveTheme(theme: Theme) {
  try { window.localStorage.setItem(storageKey, theme) } catch { /* Keep the in-memory preference. */ }
}
