// src/auth/AuthProvider.tsx
/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { logoutUser, subscribeToUnauthorizedLogout } from "../api";
import type { CognitoTokens } from "../types/api";
import {
    clearSession as clearStoredSession,
    getSession as getStoredSession,
    setSessionFromTokens,
    subscribe as subscribeAuthSession,
} from "./tokenManager";

export type AuthContextValue = {
    accessToken: string | null;
    idToken: string | null;
    refreshToken: string | null;
    isAuthenticated: boolean;
    isReady: boolean;

    setSession: (tokens: CognitoTokens | null) => void;
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
    const [session, setSessionState] = useState(() => getStoredSession());
    const [isReady, setIsReady] = useState(false);

    const markJustLoggedOut = useCallback(() => {
        try {
            sessionStorage.setItem("jt.justLoggedOut", "1");
        } catch {
            // ignore
        }
    }, []);

    // Hydrate tokens on app start + keep tab state in sync
    useEffect(() => {
        const syncSession = () => setSessionState(getStoredSession());
        const unsubscribeSession = subscribeAuthSession(syncSession);
        const readyTimer = window.setTimeout(() => setIsReady(true), 0);
        const unsubscribe = subscribeToUnauthorizedLogout(() => {
            markJustLoggedOut();
            clearStoredSession();
            setSessionState(null);
        });
        return () => {
            unsubscribeSession();
            unsubscribe();
            clearTimeout(readyTimer);
        };
    }, [markJustLoggedOut]);

    function setSession(tokens: CognitoTokens | null) {
        if (tokens) {
            setSessionFromTokens(tokens);
        } else {
            clearStoredSession();
        }
    }

    async function logout() {
        markJustLoggedOut();
        clearStoredSession();
        setSessionState(null);

        try {
            await logoutUser();
        } catch {
            // ignore
        }
    }

    function isAuthed() {
        return !!session?.accessToken;
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
            ...(session?.accessToken ? { Authorization: `Bearer ${session.accessToken}` } : {}),
        };

        const res = await fetch(`${baseUrl}${path}`, {
            ...options,
            headers,
            credentials: "omit",
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
        accessToken: session?.accessToken ?? null,
        idToken: session?.idToken ?? null,
        refreshToken: session?.refreshToken ?? null,
        isAuthenticated: !!session?.accessToken,
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


