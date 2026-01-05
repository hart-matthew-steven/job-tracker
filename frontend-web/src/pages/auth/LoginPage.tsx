// src/pages/auth/LoginPage.tsx
import { useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { cognitoLogin, sendEmailVerificationCode } from "../../api/authCognito";
import { useAuth } from "../../auth/AuthProvider";
import { useToast } from "../../components/ui/toast";
import { ROUTES } from "../../routes/paths";
import type { CognitoTokens } from "../../types/api";
import { getCurrentUser } from "../../api";

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v || v === "/") return ROUTES.board;
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return ROUTES.board;
}

export default function LoginPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();

  const next = useMemo(() => safeNext(searchParams.get("next")), [searchParams]);

  const { setSession } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function completeLogin(tokens: CognitoTokens | null | undefined) {
    if (!tokens?.access_token) {
      throw new Error("Login did not return an access token.");
    }
    setSession(tokens);
    try {
      const me = await getCurrentUser();
      if (!me.is_email_verified) {
        await sendEmailVerificationCode({ email: me.email });
        const params = new URLSearchParams({ email: me.email, next });
        nav(`${ROUTES.verify}?${params.toString()}`, { replace: true });
        return;
      }
    } catch (err) {
      console.error("Unable to fetch verification status:", err);
    }
    nav(next, { replace: true });
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);

    try {
      const normalizedEmail = email.trim().toLowerCase();
      const res = await cognitoLogin(normalizedEmail, password);

      if (res.status === "OK") {
        await completeLogin(res.tokens);
        return;
      }

      if (res.status === "CHALLENGE") {
        if (!res.session) {
          throw new Error("Missing Cognito challenge session.");
        }
        const state = { email: normalizedEmail, session: res.session, next };
        if (res.next_step === "MFA_SETUP") {
          nav(ROUTES.mfaSetup, { state, replace: true });
          return;
        }
        if (res.next_step === "SOFTWARE_TOKEN_MFA") {
          nav(ROUTES.mfaChallenge, { state, replace: true });
          return;
        }
        throw new Error("Unsupported Cognito challenge. Please try again.");
      }

      throw new Error("Login failed.");
    } catch (err) {
      const errObj = err as { message?: string } | null;
      const msg = errObj?.message ?? "Login failed";
      setError(msg);
      toast.error(msg, "Login");
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
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Email</label>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder="you@example.com"
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Password</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
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
              ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500"
              : "border-slate-300 bg-slate-900 text-white hover:bg-slate-800 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800",
          ].join(" ")}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="text-sm text-slate-600 dark:text-slate-400">
        Don’t have an account?{" "}
        <NavLink to={registerLink} className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200">
          Create one
        </NavLink>
      </div>

      <div className="text-xs text-slate-500 dark:text-slate-400">
        Already registered but not confirmed? Enter the code from your email on the{" "}
        <NavLink
          to={`/verify${next ? `?next=${encodeURIComponent(next)}` : ""}`}
          className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200"
        >
          confirmation screen
        </NavLink>
        .
      </div>
    </div>
  );
}


