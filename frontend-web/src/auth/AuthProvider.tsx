// src/auth/AuthProvider.tsx
/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { getAccessToken, setAccessToken, logoutUser, subscribeToUnauthorizedLogout } from "../api";

export type AuthContextValue = {
    token: string | null;
    isAuthenticated: boolean;
    isReady: boolean;

    setSession: (newToken: string | null) => void;
    logout: () => Promise<void>;

    isAuthed: () => boolean;
    requireAuthNavigate: (nextRaw?: string) => string;

    authFetch: (path: string, options?: RequestInit & { headers?: Record<string, string> }) => Promise<Response>;
    refresh: () => Promise<boolean>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within <AuthProvider />");
    return ctx;
}

// Prevent open redirects: only allow in-app paths like "/jobs/123"
function safeNext(nextRaw: string | undefined) {
    const v = (nextRaw || "").trim();
    if (!v) return "/";
    if (v.startsWith("/") && !v.startsWith("//")) return v;
    return "/";
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
    const [token, setToken] = useState<string | null>(() => getAccessToken());
    const [isReady, setIsReady] = useState(false);

    const markJustLoggedOut = useCallback(() => {
        try {
            sessionStorage.setItem("jt.justLoggedOut", "1");
        } catch {
            // ignore
        }
    }, []);

    // Hydrate token from localStorage on app start + keep tab state in sync
    useEffect(() => {
        const sync = () => setToken(getAccessToken());
        sync();
        const readyTimer = window.setTimeout(() => setIsReady(true), 0);
        window.addEventListener("storage", sync);
        const unsubscribe = subscribeToUnauthorizedLogout(() => {
            markJustLoggedOut();
            setAccessToken(null);
            setToken(null);
        });
        return () => {
            window.removeEventListener("storage", sync);
            unsubscribe();
            clearTimeout(readyTimer);
        };
    }, [markJustLoggedOut]);

    function setSession(newToken: string | null) {
        setAccessToken(newToken);
        setToken(newToken);
    }

    // Phase 2: server logout (revokes refresh token cookie + clears local token in api.js)
    async function logout() {
        markJustLoggedOut();
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
    async function authFetch(path: string, options: RequestInit & { headers?: Record<string, string> } = {}) {
        const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

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

    const value: AuthContextValue = {
        token,
        isAuthenticated: !!token,
        isReady,

        setSession,
        logout,

        isAuthed,
        requireAuthNavigate,

        authFetch,
        refresh,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}


