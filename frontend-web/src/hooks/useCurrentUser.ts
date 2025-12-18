import { useCallback, useEffect, useMemo, useState } from "react";
import { getCurrentUser } from "../api";
import type { UserMeOut } from "../types/api";

export type UseCurrentUserResult = {
  user: UserMeOut | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  // Backwards compatible flag used by the shell/UI to label data source.
  isStub: boolean;
};

export function useCurrentUser(): UseCurrentUserResult {
  const [user, setUser] = useState<UserMeOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res: UserMeOut = await getCurrentUser();
      setUser(res ?? null);
    } catch (e) {
      setUser(null);
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Failed to load profile");
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
      isStub: false,
    }),
    [user, loading, error, reload]
  );
}


