import { useCallback, useEffect, useMemo, useState } from "react";
import { getMySettings, updateMySettings } from "../api";
import type { UpdateSettingsIn, UserSettingsOut } from "../types/api";

export type SettingsState = {
  autoRefreshSeconds: number;
  theme: string;
  defaultJobsSort: string;
  defaultJobsView: string;
  dataRetentionDays: number;
};

export type UseSettingsResult = {
  settings: SettingsState;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  setAutoRefreshSeconds: (seconds: number) => Promise<void>;
  setTheme: (theme: string) => Promise<void>;
  setDefaultJobsSort: (sort: string) => Promise<void>;
  setDefaultJobsView: (view: string) => Promise<void>;
  setDataRetentionDays: (days: number) => Promise<void>;
};

function applyThemeToDocument(rawTheme: string) {
  const desired = String(rawTheme || "dark").trim().toLowerCase() || "dark";

  function apply(theme: "dark" | "light") {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.setAttribute("data-theme", theme);
  }

  if (desired === "system") {
    const m = window.matchMedia?.("(prefers-color-scheme: dark)");
    apply(m?.matches ? "dark" : "light");
    return;
  }

  apply(desired === "light" ? "light" : "dark");
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<SettingsState>({
    autoRefreshSeconds: 0,
    theme: "dark",
    defaultJobsSort: "updated_desc",
    defaultJobsView: "all",
    dataRetentionDays: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res: UserSettingsOut = await getMySettings();
      setSettings({
        autoRefreshSeconds: Number(res?.auto_refresh_seconds ?? 0) || 0,
        theme: String(res?.theme ?? "dark") || "dark",
        defaultJobsSort: String(res?.default_jobs_sort ?? "updated_desc") || "updated_desc",
        defaultJobsView: String(res?.default_jobs_view ?? "all") || "all",
        dataRetentionDays: Number(res?.data_retention_days ?? 0) || 0,
      });
    } catch (e) {
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Failed to load settings");
      setSettings({
        autoRefreshSeconds: 0,
        theme: "dark",
        defaultJobsSort: "updated_desc",
        defaultJobsView: "all",
        dataRetentionDays: 0,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  // Apply theme immediately whenever this hook's theme value changes.
  // Important: `useSettings()` is not global state, so we apply the side-effect here
  // so the Settings page can change the theme without requiring a refresh.
  useEffect(() => {
    const raw = String(settings.theme ?? "dark");

    if (String(raw).trim().toLowerCase() !== "system") {
      applyThemeToDocument(raw);
      return;
    }

    const m = window.matchMedia?.("(prefers-color-scheme: dark)");
    const handler = () => applyThemeToDocument("system");
    handler();
    if (!m) return;
    try {
      m.addEventListener("change", handler);
      return () => m.removeEventListener("change", handler);
    } catch {
      // Safari fallback
      // eslint-disable-next-line deprecation/deprecation
      m.addListener(handler);
      // eslint-disable-next-line deprecation/deprecation
      return () => m.removeListener(handler);
    }
  }, [settings.theme]);

  return useMemo(
    () => ({
      settings,
      loading,
      error,
      reload,
      setAutoRefreshSeconds: (seconds: number) =>
        (async () => {
          const next = Number(seconds) || 0;
          setSettings((prev) => ({ ...prev, autoRefreshSeconds: next }));
          try {
            const payload: UpdateSettingsIn = {
              auto_refresh_seconds: next,
              theme: settings.theme,
              default_jobs_sort: settings.defaultJobsSort,
              default_jobs_view: settings.defaultJobsView,
              data_retention_days: settings.dataRetentionDays,
            };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            const msg = err?.message ?? "Failed to update settings";
            setError(msg);
            throw new Error(msg);
          }
        })(),
      setTheme: (theme: string) =>
        (async () => {
          const next = String(theme || "dark").trim().toLowerCase() || "dark";
          setSettings((prev) => ({ ...prev, theme: next }));
          try {
            const payload: UpdateSettingsIn = {
              auto_refresh_seconds: settings.autoRefreshSeconds,
              theme: next,
              default_jobs_sort: settings.defaultJobsSort,
              default_jobs_view: settings.defaultJobsView,
              data_retention_days: settings.dataRetentionDays,
            };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            const msg = err?.message ?? "Failed to update settings";
            setError(msg);
            throw new Error(msg);
          }
        })(),
      setDefaultJobsSort: (sort: string) =>
        (async () => {
          const next = String(sort || "updated_desc").trim() || "updated_desc";
          setSettings((prev) => ({ ...prev, defaultJobsSort: next }));
          try {
            const payload: UpdateSettingsIn = {
              auto_refresh_seconds: settings.autoRefreshSeconds,
              theme: settings.theme,
              default_jobs_sort: next,
              default_jobs_view: settings.defaultJobsView,
              data_retention_days: settings.dataRetentionDays,
            };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            const msg = err?.message ?? "Failed to update settings";
            setError(msg);
            throw new Error(msg);
          }
        })(),
      setDefaultJobsView: (view: string) =>
        (async () => {
          const next = String(view || "all").trim().toLowerCase() || "all";
          setSettings((prev) => ({ ...prev, defaultJobsView: next }));
          try {
            const payload: UpdateSettingsIn = {
              auto_refresh_seconds: settings.autoRefreshSeconds,
              theme: settings.theme,
              default_jobs_sort: settings.defaultJobsSort,
              default_jobs_view: next,
              data_retention_days: settings.dataRetentionDays,
            };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            const msg = err?.message ?? "Failed to update settings";
            setError(msg);
            throw new Error(msg);
          }
        })(),
      setDataRetentionDays: (days: number) =>
        (async () => {
          const next = Math.max(0, Number(days) || 0);
          setSettings((prev) => ({ ...prev, dataRetentionDays: next }));
          try {
            const payload: UpdateSettingsIn = {
              auto_refresh_seconds: settings.autoRefreshSeconds,
              theme: settings.theme,
              default_jobs_sort: settings.defaultJobsSort,
              default_jobs_view: settings.defaultJobsView,
              data_retention_days: next,
            };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            const msg = err?.message ?? "Failed to update settings";
            setError(msg);
            throw new Error(msg);
          }
        })(),
    }),
    [settings, loading, error, reload]
  );
}


