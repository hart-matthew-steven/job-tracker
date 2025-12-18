import { useCallback, useEffect, useMemo, useState } from "react";
import { getCurrentUser } from "../api";

export function useCurrentUser() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res = await getCurrentUser();
      setUser(res ?? null);
    } catch (e) {
      setUser(null);
      setError(e?.message ?? "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return useMemo(
    () => ({
      user,
      loading,
      error,
      reload,
      // Backwards compatible flag used by the shell/UI to label data source.
      isStub: false,
    }),
    [user, loading, error, reload]
  );
}


