const THEME_STORAGE_KEY = "jobtracker.theme";

type ThemePreference = "dark" | "light" | "system";

export function normalizeTheme(raw?: string | null): ThemePreference {
    const value = String(raw ?? "").trim().toLowerCase();
    if (value === "light" || value === "system") return value;
    return "dark";
}

export function loadStoredTheme(): ThemePreference | null {
    if (typeof window === "undefined" || !window.localStorage) return null;
    try {
        const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
        if (!stored) return null;
        return normalizeTheme(stored);
    } catch {
        return null;
    }
}

export function saveThemePreference(theme: string): void {
    if (typeof window === "undefined" || !window.localStorage) return;
    try {
        window.localStorage.setItem(THEME_STORAGE_KEY, normalizeTheme(theme));
    } catch {
        // ignore (storage might be disabled)
    }
}

export function applyThemeToDocument(rawTheme: string | null | undefined): void {
    if (typeof document === "undefined") return;
    const desired = normalizeTheme(rawTheme);

    const apply = (theme: "dark" | "light") => {
        document.documentElement.classList.toggle("dark", theme === "dark");
        document.documentElement.setAttribute("data-theme", theme);
    };

    if (desired === "system") {
        const media = typeof window !== "undefined" ? window.matchMedia?.("(prefers-color-scheme: dark)") : null;
        apply(media?.matches ? "dark" : "light");
        return;
    }

    apply(desired);
}

export function getInitialTheme(): ThemePreference {
    return loadStoredTheme() ?? "dark";
}

export { THEME_STORAGE_KEY };

