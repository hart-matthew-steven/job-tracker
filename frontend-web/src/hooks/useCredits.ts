import { useContext } from "react";

import CreditsContext, { type CreditsContextValue } from "../context/CreditsContext";

export function useCredits(): CreditsContextValue {
  const ctx = useContext(CreditsContext);
  if (!ctx) throw new Error("useCredits must be used within <CreditsProvider />");
  return ctx;
}
