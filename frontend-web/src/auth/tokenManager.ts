import API_BASE from "../lib/apiBase";
import type { CognitoTokens } from "../types/api";

export type AuthSession = {
  accessToken: string;
  idToken?: string;
  refreshToken: string | null;
  tokenType: string;
  expiresAt: number;
};

const STORAGE_KEY = "jt.auth.session";
const BROADCAST_KEY = "jt.auth.broadcast";
const EXPIRY_SKEW_MS = 60_000; // refresh one minute before expiry

let currentSession: AuthSession | null = loadSession();
let refreshPromise: Promise<AuthSession | null> | null = null;
const listeners = new Set<() => void>();

function loadSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (typeof parsed?.accessToken === "string" && typeof parsed?.expiresAt === "number") {
      return parsed;
    }
  } catch {
    // ignore parse errors
  }
  return null;
}

function persistSession(session: AuthSession | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!session) sessionStorage.removeItem(STORAGE_KEY);
    else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    localStorage.setItem(BROADCAST_KEY, String(Date.now()));
  } catch {
    // storage may be unavailable (Safari private mode, etc.)
  }
}

function notify(): void {
  listeners.forEach((listener) => {
    try {
      listener();
    } catch {
      // ignore listener failures
    }
  });
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (!event.key) return;
    if (event.key === STORAGE_KEY || event.key === BROADCAST_KEY) {
      currentSession = loadSession();
      notify();
    }
  });
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSession(): AuthSession | null {
  return currentSession;
}

export function getAccessToken(): string | null {
  return currentSession?.accessToken ?? null;
}

export function setSessionFromTokens(tokens: CognitoTokens, fallbackRefresh?: string | null): void {
  const refreshToken = tokens.refresh_token ?? fallbackRefresh ?? currentSession?.refreshToken ?? null;
  const expiresInMs = Math.max(5_000, (tokens.expires_in || 0) * 1000 - EXPIRY_SKEW_MS);

  currentSession = {
    accessToken: tokens.access_token,
    idToken: tokens.id_token ?? undefined,
    refreshToken,
    tokenType: tokens.token_type || "Bearer",
    expiresAt: Date.now() + expiresInMs,
  };
  persistSession(currentSession);
  notify();
}

export function clearSession(): void {
  currentSession = null;
  persistSession(null);
  notify();
}

export function isAccessTokenExpiring(skewMs = EXPIRY_SKEW_MS): boolean {
  if (!currentSession) return true;
  return Date.now() >= currentSession.expiresAt - skewMs;
}

export async function ensureValidAccessToken(): Promise<string | null> {
  if (!currentSession) return null;
  if (!isAccessTokenExpiring()) {
    return currentSession.accessToken;
  }
  const session = await refreshSession();
  return session?.accessToken ?? null;
}

export async function refreshSession(): Promise<AuthSession | null> {
  if (!currentSession?.refreshToken) {
    clearSession();
    return null;
  }
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/cognito/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: currentSession?.refreshToken }),
        credentials: "include",
      });

      if (!res.ok) {
        clearSession();
        return null;
      }

      const data = await res.json().catch(() => null);
      if (!data || data.status !== "OK" || !data.tokens?.access_token) {
        clearSession();
        return null;
      }

      setSessionFromTokens(data.tokens, currentSession?.refreshToken ?? null);
      return currentSession;
    } catch {
      clearSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

