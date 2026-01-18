import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PropsWithChildren, ReactElement } from "react";

import { getCreditsBalance } from "../api";
import type { CreditsBalance } from "../types/api";

export type CreditsContextValue = {
  balance: CreditsBalance | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const CreditsContext = createContext<CreditsContextValue | null>(null);

export function CreditsProvider({ children }: PropsWithChildren): ReactElement {
  const [balance, setBalance] = useState<CreditsBalance | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latestRequest = useRef(0);

  const refresh = useCallback(async () => {
    const requestId = latestRequest.current + 1;
    latestRequest.current = requestId;
    setLoading(true);
    try {
      const data = await getCreditsBalance();
      if (latestRequest.current !== requestId) return;
      setBalance(data);
      setError(null);
    } catch (err) {
      if (latestRequest.current !== requestId) return;
      const message = (err as Error)?.message || "Unable to load credits";
      setError(message);
    } finally {
      if (latestRequest.current === requestId) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<CreditsContextValue>(
    () => ({ balance, loading, error, refresh }),
    [balance, loading, error, refresh]
  );

  return <CreditsContext.Provider value={value}>{children}</CreditsContext.Provider>;
}

export default CreditsContext;
