import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearSession,
  getSession,
  refreshSession,
  setSessionFromTokens,
} from "./tokenManager";
import type { CognitoTokens } from "../types/api";

const TOKENS: CognitoTokens = {
  access_token: "access-1",
  id_token: "id-1",
  refresh_token: "refresh-1",
  expires_in: 3600,
  token_type: "Bearer",
};

function makeStorage(): Storage {
  const store = new Map<string, string>();
  const storage: Partial<Storage> = {
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    get length() {
      return store.size;
    },
  };
  return storage as Storage;
}

describe("tokenManager", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", makeStorage());
    vi.stubGlobal("localStorage", makeStorage());
    clearSession();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("persists sessions to sessionStorage and exposes accessor", () => {
    expect(getSession()).toBeNull();

    setSessionFromTokens(TOKENS);

    const stored = getSession();
    expect(stored).not.toBeNull();
    expect(stored?.accessToken).toBe("access-1");
    expect(stored?.refreshToken).toBe("refresh-1");
    expect(JSON.parse(sessionStorage.getItem("jt.auth.session") ?? "{}").accessToken).toBe("access-1");
  });

  it("deduplicates concurrent refresh calls", async () => {
    setSessionFromTokens(TOKENS);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          status: "OK",
          tokens: {
            access_token: "access-2",
            id_token: "id-2",
            expires_in: 3600,
            token_type: "Bearer",
          },
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const p1 = refreshSession();
    const p2 = refreshSession();

    const [sessionA, sessionB] = await Promise.all([p1, p2]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sessionA?.accessToken).toBe("access-2");
    expect(sessionB?.accessToken).toBe("access-2");
    expect(getSession()?.accessToken).toBe("access-2");
  });

  it("clears session when refresh fails", async () => {
    setSessionFromTokens(TOKENS);

    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ message: "invalid" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const refreshed = await refreshSession();

    expect(refreshed).toBeNull();
    expect(getSession()).toBeNull();
    expect(sessionStorage.getItem("jt.auth.session")).toBeNull();
  });
});

