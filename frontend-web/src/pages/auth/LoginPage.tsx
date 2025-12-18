// src/pages/auth/LoginPage.tsx
import { useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { loginUser } from "../../api";
import { useAuth } from "../../auth/AuthProvider";

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function LoginPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();

  const next = useMemo(() => safeNext(searchParams.get("next")), [searchParams]);

  const { setSession } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);

    try {
      const res = await loginUser({
        email: email.trim(),
        password,
      });

      if (!res?.access_token) {
        throw new Error("Login did not return an access token.");
      }

      // ✅ update auth state first, then navigate
      setSession(res.access_token);
      nav(next, { replace: true });
    } catch (err) {
      const errObj = err as { message?: string } | null;
      setError(errObj?.message ?? "Login failed");
    } finally {
      setBusy(false);
    }
  }

  const registerLink = `/register${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-200">Email</label>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-700"
            placeholder="you@example.com"
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-200">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-700"
            placeholder="••••••••"
            disabled={busy}
            required
          />
        </div>

        <button
          type="submit"
          disabled={busy}
          className={[
            "w-full rounded-lg px-3 py-2 text-sm font-semibold transition border",
            busy
              ? "cursor-not-allowed border-slate-800 bg-slate-900/40 text-slate-500"
              : "border-slate-700 bg-slate-800/70 text-slate-100 hover:bg-slate-800",
          ].join(" ")}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="text-sm text-slate-400">
        Don’t have an account?{" "}
        <NavLink to={registerLink} className="text-blue-300 hover:text-blue-200 font-semibold">
          Create one
        </NavLink>
      </div>

      <div className="text-xs text-slate-500">
        If you already registered but haven’t verified your email yet, open the
        verification link printed in your backend console (dev).
      </div>
    </div>
  );
}


