// src/pages/auth/RedirectIfAuthed.tsx
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";
import { ROUTES } from "../../routes/paths";

type Props = { children: ReactNode };

/**
 * If already authenticated, prevent visiting auth pages.
 * Sends user to `next` if present, otherwise "/".
 */
function normalizeNextPath(nextRaw: string | null): string {
    const v = (nextRaw || "").trim();
    if (!v || v === "/") return ROUTES.board;
    if (v.startsWith("/") && !v.startsWith("//")) return v;
    return ROUTES.board;
}

export default function RedirectIfAuthed({ children }: Props) {
    const { isAuthenticated } = useAuth();
    const location = useLocation();

    if (!isAuthenticated) return (children as ReactNode);

    const params = new URLSearchParams(location.search);
    const next = normalizeNextPath(params.get("next"));
    return <Navigate to={next} replace />;
}


