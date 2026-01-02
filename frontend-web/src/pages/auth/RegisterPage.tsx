// src/pages/auth/RegisterPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import type { FormEvent } from "react";

import { cognitoSignup } from "../../api/authCognito";
import { useToast } from "../../components/ui/toast";
import { evaluatePassword, describeViolation, PASSWORD_MIN_LENGTH, type PasswordViolation } from "../../lib/passwordPolicy";
import PasswordRequirements from "../../components/forms/PasswordRequirements";

declare global {
  interface Window {
    turnstile?: {
      render: (container: HTMLElement, options: Record<string, unknown>) => string;
      execute: (widgetId: string) => void;
      reset: (widgetId: string) => void;
    };
    __TURNSTILE_SITE_KEY__?: string;
  }
}

const TURNSTILE_SCRIPT_ID = "cf-turnstile-script";
const TURNSTILE_API_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

function resolveTurnstileSiteKey(): string {
  const override = typeof window !== "undefined" ? window.__TURNSTILE_SITE_KEY__ ?? "" : "";
  const fromEnv = (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "").trim();
  return (override || fromEnv).trim();
}

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
  const turnstileSiteKey = resolveTurnstileSiteKey();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [serverViolations, setServerViolations] = useState<PasswordViolation[]>([]);
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileContainerRef = useRef<HTMLDivElement | null>(null);
  const turnstileWidgetIdRef = useRef<string | null>(null);
  const pendingTurnstileRef = useRef<{ resolve: (token: string) => void; reject: (err: Error) => void } | null>(null);

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

  useEffect(() => {
    if (!turnstileSiteKey || !turnstileContainerRef.current) {
      return;
    }

    let cancelled = false;

    const emitError = (message: string) => {
      if (cancelled) return;
      const err = new Error(message);
      setError(err.message);
      toast.error(err.message, "Register");
      pendingTurnstileRef.current?.reject(err);
      pendingTurnstileRef.current = null;
      setTurnstileToken("");
    };

    const renderWidget = () => {
      if (!window.turnstile || !turnstileContainerRef.current || turnstileWidgetIdRef.current || cancelled) {
        return;
      }
      turnstileWidgetIdRef.current = window.turnstile.render(turnstileContainerRef.current, {
        sitekey: turnstileSiteKey,
        size: "invisible",
        callback: (token: string) => {
          if (cancelled) return;
          setTurnstileToken(token);
          pendingTurnstileRef.current?.resolve(token);
          pendingTurnstileRef.current = null;
        },
        "error-callback": () => emitError("Verification failed. Please try again."),
        "timeout-callback": () => emitError("Verification timed out. Please try again."),
      }) as string;
    };

    const handleScriptLoad = () => {
      const script = document.getElementById(TURNSTILE_SCRIPT_ID);
      if (script) {
        script.setAttribute("data-loaded", "true");
      }
      renderWidget();
    };

    const handleScriptError = () => emitError("Unable to load verification. Please try again later.");

    if (window.turnstile) {
      renderWidget();
    } else {
      let script = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null;
      if (!script) {
        script = document.createElement("script");
        script.id = TURNSTILE_SCRIPT_ID;
        script.src = TURNSTILE_API_URL;
        script.async = true;
        script.defer = true;
        script.onload = handleScriptLoad;
        script.onerror = handleScriptError;
        document.body.appendChild(script);
      } else if (script.getAttribute("data-loaded") === "true") {
        renderWidget();
      } else {
        script.addEventListener("load", handleScriptLoad, { once: true });
        script.addEventListener("error", handleScriptError, { once: true });
      }
    }

    return () => {
      cancelled = true;
    };
  }, [turnstileSiteKey, toast]);

  async function requestTurnstileToken(): Promise<string> {
    if (!turnstileSiteKey) {
      throw new Error("Signup is temporarily unavailable.");
    }
    if (turnstileToken) {
      return turnstileToken;
    }
    if (!window.turnstile || !turnstileWidgetIdRef.current) {
      throw new Error("Verification is still loading. Please wait a moment and try again.");
    }

    return new Promise<string>((resolve, reject) => {
      pendingTurnstileRef.current = { resolve, reject };
      try {
        window.turnstile.execute(turnstileWidgetIdRef.current!);
      } catch (_err) {
        pendingTurnstileRef.current = null;
        reject(new Error("Verification failed. Please try again."));
      }
    });
  }

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
    let captchaToken: string | null = null;
    try {
      captchaToken = await requestTurnstileToken();
    } catch (err) {
      const msg = (err as { message?: string } | null)?.message ?? "Verification failed. Please try again.";
      setError(msg);
      toast.error(msg, "Register");
      setBusy(false);
      return;
    }

    try {
      const res = await cognitoSignup({ name: eName, email: eEmail, password, turnstile_token: captchaToken });
      const status = (res?.status ?? "CONFIRMATION_REQUIRED").toUpperCase();
      const successMessage =
        status === "CONFIRMATION_REQUIRED"
          ? "Account created. Enter the verification code we emailed you."
          : res?.message ?? "Account created.";
      setMessage(successMessage);
      toast.success(successMessage, "Register");
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
      if (captchaToken && window.turnstile && turnstileWidgetIdRef.current) {
        window.turnstile.reset(turnstileWidgetIdRef.current);
      }
      setTurnstileToken("");
    }
  }

  const loginLink = `/login?next=${encodeURIComponent(next)}`;
  const signupDisabled = !turnstileSiteKey;

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

      {signupDisabled && (
        <div className="rounded-lg border border-amber-500/60 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
          Signup is temporarily unavailable because bot verification is not configured.
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Name</label>
          <input
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-slate-700"
            placeholder="Your name"
            disabled={busy}
            required
          />
        </div>

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

        <button
          type="submit"
          disabled={busy || signupDisabled}
          className={[
            "w-full rounded-lg px-3 py-2 text-sm font-semibold transition border",
            busy
              ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500"
              : "border-slate-300 bg-slate-900 text-white hover:bg-slate-800 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800",
          ].join(" ")}
        >
          {busy ? "Creating account…" : "Create account"}
        </button>
        <div ref={turnstileContainerRef} className="hidden" aria-hidden="true" />
      </form>

      <div className="text-sm text-slate-600 dark:text-slate-400">
        Already have an account?{" "}
        <NavLink
          to={loginLink}
          className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200"
        >
          Sign in
        </NavLink>
      </div>

      <div className="text-xs text-slate-500 dark:text-slate-400">
        After registration, check your inbox (and spam) for the Cognito verification code. Keep this page open so you can
        enter the code immediately.
      </div>
    </div>
  );
}


