// src/pages/auth/VerifyEmailPage.tsx
import { useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { cognitoConfirm } from "../../api/authCognito";
import { useToast } from "../../components/ui/toast";

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();

  const next = useMemo(() => safeNext(params.get("next")), [params]);
  const [email, setEmail] = useState(() => params.get("email")?.trim().toLowerCase() ?? "");
  const [code, setCode] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setMessage("");

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      const msg = "Email is required.";
      setError(msg);
      toast.error(msg, "Confirm");
      return;
    }
    if (!code.trim()) {
      const msg = "Enter the 6-digit code from your email.";
      setError(msg);
      toast.error(msg, "Confirm");
      return;
    }

    setBusy(true);
    try {
      const res = await cognitoConfirm({ email: normalizedEmail, code: code.trim() });
      const successMsg = res?.message ?? "Account verified. You can now sign in.";
      setMessage(successMsg);
      toast.success(successMsg, "Confirm");
      nav(`/login?next=${encodeURIComponent(next)}`, { replace: true });
    } catch (err) {
      const apiErr = err as { message?: string } | null;
      const msg = apiErr?.message ?? "Confirmation failed";
      setError(msg);
      toast.error(msg, "Confirm");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-sm text-emerald-200">
          {message}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder="you@example.com"
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Verification code</label>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder="6-digit code"
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
          {busy ? "Confirming…" : "Confirm account"}
        </button>
      </form>

      <div className="text-xs text-slate-500 dark:text-slate-400">
        Didn’t receive the email? Check spam or wait a minute before requesting another signup. You can restart the flow{" "}
        <NavLink
          to={`/register?next=${encodeURIComponent(next)}`}
          className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200"
        >
          from the signup page
        </NavLink>
        .
      </div>
    </div>
  );
}


