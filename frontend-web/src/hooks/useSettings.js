import { useCallback, useEffect, useMemo, useState } from "react";
import { getMySettings, updateMySettings } from "../api";

export function useSettings() {
  const [settings, setSettings] = useState({ autoRefreshSeconds: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res = await getMySettings();
      setSettings({
        autoRefreshSeconds: Number(res?.auto_refresh_seconds ?? 0) || 0,
      });
    } catch (e) {
      setError(e?.message ?? "Failed to load settings");
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
      setAutoRefreshSeconds: (seconds) =>
        (async () => {
          const next = Number(seconds) || 0;
          setSettings((prev) => ({ ...prev, autoRefreshSeconds: next }));
          try {
            await updateMySettings({ auto_refresh_seconds: next });
          } catch (e) {
            setError(e?.message ?? "Failed to update settings");
          }
        })(),
    }),
    [settings, loading, error, reload]
  );
}


