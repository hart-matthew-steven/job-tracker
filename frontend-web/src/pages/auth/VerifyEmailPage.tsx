// src/pages/auth/VerifyEmailPage.tsx
import { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { Params } from "react-router-dom";

import { resendVerification, verifyEmail } from "../../api";
import { useToast } from "../../components/ui/toast";

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function VerifyEmailPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const toast = useToast();

  const token = useMemo(() => params.get("token")?.trim() ?? "", [params]);
  const email = useMemo(() => params.get("email")?.trim() ?? "", [params]);
  const next = useMemo(() => safeNext(params.get("next")), [params]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Verify automatically when loaded from the emailed link.
  useEffect(() => {
    let cancelled = false;

    async function run() {
      setError("");
      setMessage("");

      const normalizedEmail = email.trim().toLowerCase();

      if (!token) {
        if (normalizedEmail) {
          const msg = `We emailed a verification link to ${normalizedEmail}. Check your inbox or resend it below.`;
          setMessage(msg);
        } else {
          const msg = "Missing verification token. Please use the link from your email.";
          setError(msg);
          toast.error(msg, "Verify email");
        }
        return;
      }

      setBusy(true);
      try {
        const res = await verifyEmail(token);
        if (cancelled) return;

        const msg = res?.message ?? "Email verified. You can now log in.";
        setMessage(msg);
        toast.success(msg, "Verify email");
        setTimeout(() => {
          if (!cancelled) nav(`/login?next=${encodeURIComponent(next)}`, { replace: true });
        }, 900);
      } catch (e) {
        if (cancelled) return;
        const err = e as { message?: string } | null;
        const msg = err?.message ?? "Verification failed";
        setError(msg);
        toast.error(msg, "Verify email");
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [token, nav, next, toast]);

  async function onResend() {
    setError("");
    setMessage("");

    const e = (email || "").trim().toLowerCase();
    if (!e) {
      const msg = "Missing email. Please go back to Register and resend verification.";
      setError(msg);
      toast.error(msg, "Verify email");
      return;
    }

    setBusy(true);
    try {
      const res = await resendVerification({ email: e });
      const msg = res?.message ?? "If that email exists, a verification link was sent.";
      setMessage(msg);
      toast.info(msg, "Verification");
    } catch (e2) {
      const err = e2 as { message?: string } | null;
      const msg = err?.message ?? "Resend failed";
      setError(msg);
      toast.error(msg, "Verification");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-600 dark:text-slate-300">{busy ? "Verifying…" : "Email verification"}</div>

      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
          <div className="mt-2 flex items-center justify-between gap-3">
            <NavLink to={`/login?next=${encodeURIComponent(next)}`} className="text-sm text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200">
              Back to Login
            </NavLink>
            <button
              type="button"
              onClick={onResend}
              disabled={busy || !email}
              className={[
                "rounded-lg px-3 py-2 text-xs font-semibold transition border",
                busy || !email
                  ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900",
              ].join(" ")}
            >
              Resend verification
            </button>
          </div>
        </div>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-sm text-emerald-200">
          {message}
          <div className="mt-2 text-xs text-slate-600 dark:text-slate-300">
            Redirecting to{" "}
            <NavLink className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200" to={`/login?next=${encodeURIComponent(next)}`}>
              Login
            </NavLink>
            …
          </div>
        </div>
      )}
    </div>
  );
}


