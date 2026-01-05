// src/pages/auth/VerifyEmailPage.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { confirmEmailVerificationCode, sendEmailVerificationCode } from "../../api/authCognito";
import { useToast } from "../../components/ui/toast";
import { getSession } from "../../auth/tokenManager";
import { ROUTES } from "../../routes/paths";

const RESEND_COOLDOWN_SECONDS = 60;

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v || v === "/") return ROUTES.board;
  if (!/^\//.test(v) || v.startsWith("//")) {
    return ROUTES.board;
  }
  return v;
}

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();

  const initialSent = useMemo(() => params.get("sent") === "1", [params]);
  const next = useMemo(() => safeNext(params.get("next")), [params]);
  const [email, setEmail] = useState(() => params.get("email")?.trim().toLowerCase() ?? "");
  const [code, setCode] = useState("");

  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState(initialSent ? "We just sent a verification code. Check your email." : "");
  const [cooldownUntil, setCooldownUntil] = useState<number>(() =>
    initialSent ? Date.now() + RESEND_COOLDOWN_SECONDS * 1000 : 0
  );
  const [nowTs, setNowTs] = useState(() => Date.now());
  const [hadSession] = useState(() => {
    try {
      return !!getSession()?.accessToken;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    const id = window.setInterval(() => setNowTs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const normalizedEmail = email.trim().toLowerCase();

  const autoSendEmailRef = useRef<string | null>(initialSent ? email : null);
  const initialSentRef = useRef(initialSent);


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
      const res = await confirmEmailVerificationCode({ email: normalizedEmail, code: code.trim() });
      const successMsg = res?.message ?? "Email verified. You can continue.";
      setMessage(successMsg);
      toast.success(successMsg, "Confirm");
      if (hadSession) {
        nav(next, { replace: true });
      } else {
        nav(`/login?next=${encodeURIComponent(next)}`, { replace: true });
      }
    } catch (err) {
      const apiErr = err as { message?: string } | null;
      const msg = apiErr?.message ?? "Confirmation failed";
      setError(msg);
      toast.error(msg, "Confirm");
    } finally {
      setBusy(false);
    }
  }

  const handleSend = useCallback(async (initial = false) => {
    if (!normalizedEmail) {
      if (!initial) {
        const msg = "Enter your email first.";
        setError(msg);
        toast.error(msg, "Verification");
      }
      return;
    }
    const now = Date.now();
    if (!initial && cooldownUntil > now) {
      return;
    }
    setSending(true);
    try {
      const res = await sendEmailVerificationCode({ email: normalizedEmail });
      const msg = res?.message ?? "Verification code sent.";
      setMessage(msg);
      toast.success(msg, "Verification");
      if (res?.resend_available_in_seconds && res.resend_available_in_seconds > 0) {
        setCooldownUntil(Date.now() + res.resend_available_in_seconds * 1000);
      } else {
        setCooldownUntil(now + RESEND_COOLDOWN_SECONDS * 1000);
      }
    } catch (err) {
      const apiErr = err as { message?: string } | null;
      const msg = apiErr?.message ?? "Unable to send verification code.";
      setError(msg);
      toast.error(msg, "Verification");
    } finally {
      setSending(false);
    }
  }, [normalizedEmail, cooldownUntil, toast]);

  useEffect(() => {
    if (!normalizedEmail) return;
    if (cooldownUntil !== 0) return;
    if (initialSentRef.current) return;
    if (autoSendEmailRef.current === normalizedEmail) return;
    autoSendEmailRef.current = normalizedEmail;
    void handleSend(true);
  }, [normalizedEmail, cooldownUntil, initialSent, handleSend]);

  const cooldownRemaining = Math.max(0, Math.ceil((cooldownUntil - nowTs) / 1000));

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
            autoComplete="one-time-code"
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
        <button
          type="button"
          onClick={() => void handleSend()}
          disabled={sending || busy || !normalizedEmail || cooldownRemaining > 0}
          className="w-full rounded-lg border border-slate-400 bg-transparent px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-200 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
        >
          {sending ? "Sending…" : cooldownRemaining > 0 ? `Resend available in ${cooldownRemaining}s` : "Resend code"}
        </button>
      </form>

      <div className="text-xs text-slate-500 dark:text-slate-400">
        Didn’t receive the email? Check spam, then tap “Resend code”. Need to change email?{" "}
        <NavLink to={`/register?next=${encodeURIComponent(next)}`} className="text-blue-500 hover:text-blue-300">
          Restart signup
        </NavLink>
        .
      </div>
    </div>
  );
}


