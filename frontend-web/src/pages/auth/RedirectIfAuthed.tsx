// src/pages/auth/RedirectIfAuthed.tsx
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthProvider";

type Props = { children: ReactNode };

/**
 * If already authenticated, prevent visiting auth pages.
 * Sends user to `next` if present, otherwise "/".
 */
export default function RedirectIfAuthed({ children }: Props) {
    const { isAuthenticated } = useAuth();
    const location = useLocation();

    if (!isAuthenticated) return (children as ReactNode);

    const params = new URLSearchParams(location.search);
    const next = params.get("next");
    return <Navigate to={next || "/"} replace />;
}


