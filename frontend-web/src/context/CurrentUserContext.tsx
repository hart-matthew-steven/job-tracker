import type { ReactNode } from "react";
import type { UseCurrentUserResult } from "../hooks/useCurrentUser";
import { CurrentUserContext } from "./CurrentUserContext.shared";

type ProviderProps = {
  value: UseCurrentUserResult;
  children: ReactNode;
};

export function CurrentUserProvider({ value, children }: ProviderProps) {
  return <CurrentUserContext.Provider value={value}>{children}</CurrentUserContext.Provider>;
}

