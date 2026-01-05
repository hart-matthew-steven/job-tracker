import { useContext } from "react";
import type { UseCurrentUserResult } from "../hooks/useCurrentUser";
import { CurrentUserContext } from "./CurrentUserContext.shared";

export function useCurrentUserContext(): UseCurrentUserResult {
  const ctx = useContext(CurrentUserContext);
  if (!ctx) {
    throw new Error("useCurrentUserContext must be used within CurrentUserProvider");
  }
  return ctx;
}

