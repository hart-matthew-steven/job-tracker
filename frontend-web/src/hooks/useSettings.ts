import { useCallback, useEffect, useMemo, useState } from "react";
import { getMySettings, updateMySettings } from "../api";
import type { UpdateSettingsIn, UserSettingsOut } from "../types/api";

export type SettingsState = {
  autoRefreshSeconds: number;
};

export type UseSettingsResult = {
  settings: SettingsState;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  setAutoRefreshSeconds: (seconds: number) => Promise<void>;
};

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<SettingsState>({ autoRefreshSeconds: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res: UserSettingsOut = await getMySettings();
      setSettings({
        autoRefreshSeconds: Number(res?.auto_refresh_seconds ?? 0) || 0,
      });
    } catch (e) {
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Failed to load settings");
      setSettings({ autoRefreshSeconds: 0 });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

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
            const payload: UpdateSettingsIn = { auto_refresh_seconds: next };
            await updateMySettings(payload);
          } catch (e) {
            const err = e as { message?: string } | null;
            setError(err?.message ?? "Failed to update settings");
          }
        })(),
    }),
    [settings, loading, error, reload]
  );
}


