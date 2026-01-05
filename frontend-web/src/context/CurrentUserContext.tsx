import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { UseCurrentUserResult } from "../hooks/useCurrentUser";

const CurrentUserContext = createContext<UseCurrentUserResult | null>(null);

type ProviderProps = {
  value: UseCurrentUserResult;
  children: ReactNode;
};

export function CurrentUserProvider({ value, children }: ProviderProps) {
  return <CurrentUserContext.Provider value={value}>{children}</CurrentUserContext.Provider>;
}

export function useCurrentUserContext(): UseCurrentUserResult {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error("useCurrentUserContext must be used within CurrentUserProvider");
  }
  return ctx;
}


