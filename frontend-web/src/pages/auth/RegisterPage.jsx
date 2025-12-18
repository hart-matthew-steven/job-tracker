// src/pages/auth/RegisterPage.jsx
import { useMemo, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";

import { registerUser, resendVerification } from "../../api";

function safeNext(nextRaw) {
  const v = (nextRaw || "").trim();
  if (!v) return "/";
  if (v.startsWith("/") && !v.startsWith("//")) return v;
  return "/";
}

export default function RegisterPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();

  const next = useMemo(() => safeNext(searchParams.get("next")), [searchParams]);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setMessage("");

    const eName = name.trim();
    const eEmail = email.trim().toLowerCase();

    if (!eName) {
      setError("Name is required.");
      return;
    }
    if (!eEmail) {
      setError("Email is required.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== password2) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      const res = await registerUser({ name: eName, email: eEmail, password });
      setMessage(res?.message ?? "Registered. Please verify your email.");

      // Send user to Verify page so they can resend if needed.
      nav(
        `/verify?email=${encodeURIComponent(eEmail)}&next=${encodeURIComponent(next)}`,
        { replace: true }
      );
    } catch (err) {
      setError(err?.message ?? "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setError("");
    setMessage("");

    const eEmail = email.trim().toLowerCase();
    if (!eEmail) {
      setError("Enter your email above first.");
      return;
    }

    setBusy(true);
    try {
      const res = await resendVerification({ email: eEmail });
      setMessage(
        res?.message ?? "If that email exists, a verification link was sent."
      );
    } catch (err) {
      setError(err?.message ?? "Resend failed");
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
          <label className="block text-sm font-medium text-slate-200">
            Name
          </label>
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-700"
            placeholder="Your name"
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-200">
            Email
          </label>
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
          <label className="block text-sm font-medium text-slate-200">
            Password
          </label>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-700"
            placeholder="Min 8 characters"
            disabled={busy}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-200">
            Confirm password
          </label>
          <input
            type="password"
            autoComplete="new-password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-700"
            placeholder="Repeat password"
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
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-slate-400">
          Already have an account?{" "}
          <NavLink
            to={loginLink}
            className="text-blue-300 hover:text-blue-200 font-semibold"
          >
            Sign in
          </NavLink>
        </div>

        <button
          type="button"
          onClick={onResend}
          disabled={busy}
          className={[
            "rounded-lg px-3 py-2 text-xs font-semibold transition border",
            busy
              ? "cursor-not-allowed border-slate-800 bg-slate-900/40 text-slate-500"
              : "border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-900",
          ].join(" ")}
          title="Sends a new verification email"
        >
          Resend verification
        </button>
      </div>

      <div className="text-xs text-slate-500">
        We’ll email you a verification link. If you don’t see it, check spam or resend.
      </div>
    </div>
  );
}