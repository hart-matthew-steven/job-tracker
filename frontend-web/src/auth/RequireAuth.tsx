// src/auth/RequireAuth.tsx
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

type Props = { children: ReactNode };

export default function RequireAuth({ children }: Props) {
  const { isReady, isAuthenticated } = useAuth();
  const location = useLocation();

  // While AuthProvider is hydrating localStorage token
  if (!isReady) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-sm text-slate-400">Loading…</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // If the user explicitly logged out, always land on /login (no `next=`).
    let justLoggedOut = false;
    try {
      const flagged = sessionStorage.getItem("jt.justLoggedOut");
      if (flagged) {
        sessionStorage.removeItem("jt.justLoggedOut");
        justLoggedOut = true;
      }
    } catch {
      // ignore
    }

    if (justLoggedOut) return <Navigate to="/login" replace />;

    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return children;
}


