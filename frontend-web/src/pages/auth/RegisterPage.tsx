// src/pages/auth/RegisterPage.tsx
import { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { registerUser, resendVerification } from "../../api";
import { useToast } from "../../components/ui/toast";
import { evaluatePassword, describeViolation, PASSWORD_MIN_LENGTH, type PasswordViolation } from "../../lib/passwordPolicy";
import PasswordRequirements from "../../components/forms/PasswordRequirements";

function safeNext(nextRaw: string | null) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function RegisterPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();

  const next = useMemo(() => safeNext(searchParams.get("next")), [searchParams]);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [serverViolations, setServerViolations] = useState<PasswordViolation[]>([]);

  const normalizedName = name.trim();
  const normalizedEmail = email.trim().toLowerCase();

  const clientViolations = useMemo(
    () => evaluatePassword(password, { email: normalizedEmail, name: normalizedName }),
    [password, normalizedEmail, normalizedName]
  );
  const violationSet = useMemo(
    () => new Set<PasswordViolation>([...clientViolations, ...serverViolations]),
    [clientViolations, serverViolations]
  );

  useEffect(() => {
    setServerViolations([]);
  }, [password, normalizedEmail, normalizedName]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setMessage("");

    const eName = normalizedName;
    const eEmail = normalizedEmail;

    if (!eName) {
      const msg = "Name is required.";
      setError(msg);
      toast.error(msg, "Register");
      return;
    }
    if (!eEmail) {
      const msg = "Email is required.";
      setError(msg);
      toast.error(msg, "Register");
      return;
    }
    if (clientViolations.length > 0) {
      const msg = "Password does not meet requirements.";
      setError(msg);
      setServerViolations(clientViolations);
      toast.error(msg, "Register");
      return;
    }
    if (password !== password2) {
      const msg = "Passwords do not match.";
      setError(msg);
      toast.error(msg, "Register");
      return;
    }

    setBusy(true);
    try {
      const res = await registerUser({ name: eName, email: eEmail, password });
      setMessage(res?.message ?? "Registered. Please verify your email.");
      toast.success(res?.message ?? "Registered. Please verify your email.", "Register");

      // Send user to Verify page so they can resend if needed.
      nav(`/verify?email=${encodeURIComponent(eEmail)}&next=${encodeURIComponent(next)}`, { replace: true });
    } catch (err) {
      const apiErr = err as { message?: string; detail?: { code?: string; violations?: string[] } } | null;
      if (apiErr?.detail && apiErr.detail.code === "WEAK_PASSWORD") {
        const violations = (apiErr.detail.violations ?? []) as PasswordViolation[];
        setServerViolations(violations);
        const msg = "Password does not meet requirements.";
        setError(msg);
        toast.error(msg, "Register");
      } else {
        const msg = apiErr?.message ?? "Registration failed";
        setError(msg);
        toast.error(msg, "Register");
      }
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setError("");
    setMessage("");

    const eEmail = email.trim().toLowerCase();
    if (!eEmail) {
      const msg = "Enter your email above first.";
      setError(msg);
      toast.error(msg, "Register");
      return;
    }

    setBusy(true);
    try {
      const res = await resendVerification({ email: eEmail });
      setMessage(res?.message ?? "If that email exists, a verification link was sent.");
      toast.info(res?.message ?? "If that email exists, a verification link was sent.", "Verification");
    } catch (err) {
      const errObj = err as { message?: string } | null;
      const msg = errObj?.message ?? "Resend failed";
      setError(msg);
      toast.error(msg, "Verification");
    } finally {
      setBusy(false);
    }
  }

  const loginLink = `/login?next=${encodeURIComponent(next)}`;

  return (
    <div className="space-y-5">
      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 px-3 py-2 text-sm text-emerald-200">
          {message}
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Name</label>
          <input type="text" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700" placeholder="Your name" disabled={busy} required />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Email</label>
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700" placeholder="you@example.com" disabled={busy} required />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Password</label>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder={`At least ${PASSWORD_MIN_LENGTH} characters`}
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Confirm password</label>
          <input
            type="password"
            autoComplete="new-password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder="Repeat password"
            disabled={busy}
            required
          />
        </div>

        <PasswordRequirements violations={violationSet} minLength={PASSWORD_MIN_LENGTH} />

        {serverViolations.length > 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
            <div className="font-semibold">Fix the following:</div>
            <ul className="mt-1 list-disc pl-4">
              {Array.from(new Set(serverViolations)).map((code) => (
                <li key={code}>{describeViolation(code)}</li>
              ))}
            </ul>
          </div>
        )}

        <button type="submit" disabled={busy} className={[ "w-full rounded-lg px-3 py-2 text-sm font-semibold transition border", busy ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500" : "border-slate-300 bg-slate-900 text-white hover:bg-slate-800 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800", ].join(" ")}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-slate-600 dark:text-slate-400">
          Already have an account?{" "}
          <NavLink to={loginLink} className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200">
            Sign in
          </NavLink>
        </div>

        <button type="button" onClick={onResend} disabled={busy} className={[ "rounded-lg px-3 py-2 text-xs font-semibold transition border", busy ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900", ].join(" ")} title="Sends a new verification email">
          Resend verification
        </button>
      </div>

      <div className="text-xs text-slate-500">We’ll email you a verification link. If you don’t see it, check spam or resend.</div>
    </div>
  );
}


