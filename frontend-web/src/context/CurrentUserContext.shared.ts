import { createContext } from "react";
import type { UseCurrentUserResult } from "../hooks/useCurrentUser";

export const CurrentUserContext = createContext<UseCurrentUserResult | null>(null);

