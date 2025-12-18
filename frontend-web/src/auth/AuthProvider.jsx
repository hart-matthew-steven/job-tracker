// src/auth/AuthProvider.jsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getAccessToken, setAccessToken, logoutUser } from "../api";

const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider />");
  return ctx;
}

// Prevent open redirects: only allow in-app paths like "/jobs/123"
function safeNext(nextRaw) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getAccessToken());
  const [isReady, setIsReady] = useState(false);

  // Hydrate token from localStorage on app start + keep tab state in sync
  useEffect(() => {
    const sync = () => setToken(getAccessToken());
    sync();
    setIsReady(true);

    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  function setSession(newToken) {
    setAccessToken(newToken);
    setToken(newToken);
  }

  // Phase 2: server logout (revokes refresh token cookie + clears local token in api.js)
  async function logout() {
    // Mark that the next unauth redirect should go straight to /login (no `next=`).
    // This avoids confusing post-logout redirects like /login?next=/jobs.
    try {
      sessionStorage.setItem("jt.justLoggedOut", "1");
    } catch {
      // ignore
    }

    // Clear local auth immediately so UI updates reliably even if API call hangs/fails.
    setAccessToken(null);
    setToken(null);

    try {
      await logoutUser();
    } catch {
      // ignore
    }
  }

  function isAuthed() {
    return !!token;
  }

  function requireAuthNavigate(nextRaw = "/") {
    const next = safeNext(nextRaw);
    return `/login?next=${encodeURIComponent(next)}`;
  }

  /**
   * Use this only if you must fetch outside api.js helpers.
   * NOTE: api.js already does refresh-on-401 + retry.
   */
  async function authFetch(path, options = {}) {
    const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://matts-macbook.local:8000").replace(
      /\/$/,
      ""
    );

    const headers = {
      ...(options.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    const res = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });

    if (res.status === 401) {
      // If someone used authFetch directly and got a 401,
      // do a full logout so cookie + local state are cleaned up.
      await logout();
    }

    return res;
  }

  async function refresh() {
    // optional UI-driven refresh later; api.js already handles refresh-on-401
    return false;
  }

  const value = useMemo(
    () => ({
      token,
      isAuthenticated: !!token,
      isReady,

      setSession,
      logout,

      isAuthed,
      requireAuthNavigate,

      authFetch,
      refresh,
    }),
    [token, isReady]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}