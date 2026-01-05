import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import type { FormEvent } from "react";
import QRCode from "qrcode";

import { cognitoMfaSetup, cognitoMfaVerify } from "../../api/authCognito";
import { useAuth } from "../../auth/AuthProvider";
import { useToast } from "../../components/ui/toast";
import { ROUTES } from "../../routes/paths";
import type { CognitoTokens } from "../../types/api";

type ChallengeState = {
    email: string;
    session: string;
    next?: string;
};

export default function MfaSetupPage() {
    const location = useLocation();
    const state = location.state as ChallengeState | null;
    const nav = useNavigate();
    const toast = useToast();
    const { setSession } = useAuth();

    const email = state?.email ?? "";
    const defaultNext = useMemo(() => state?.next ?? ROUTES.dashboard, [state]);

    const [session, setSessionValue] = useState(state?.session ?? "");
    const [secret, setSecret] = useState("");
    const [otpauthUri, setOtpauthUri] = useState("");
    const [qrSrc, setQrSrc] = useState("");
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;
        async function load() {
            if (!session || secret) return;
            setError("");
            try {
                const resp = await cognitoMfaSetup({
                    session,
                    label: `JobTracker:${email || "user"}`,
                });
                if (cancelled) return;
                setSecret(resp.secret_code);
                if (resp.session) setSessionValue(resp.session);
                if (resp.otpauth_uri) {
                    const dataUrl = await QRCode.toDataURL(resp.otpauth_uri);
                    if (!cancelled) setQrSrc(dataUrl);
                    setOtpauthUri(resp.otpauth_uri);
                } else {
                    setOtpauthUri("");
                    setQrSrc("");
                }
            } catch (err) {
                if (cancelled) return;
                const msg = (err as { message?: string } | null)?.message ?? "Failed to start MFA setup.";
                setError(msg);
                toast.error(msg, "MFA setup");
            }
        }
        void load();
        return () => {
            cancelled = true;
        };
    }, [session, email, secret, toast]);

    function handleSuccess(tokens: CognitoTokens | null | undefined) {
        if (!tokens?.access_token) throw new Error("MFA verification did not return an access token.");
        setSession(tokens);
        nav(defaultNext, { replace: true });
    }

    if (!email || !session) {
        return (
            <div className="space-y-4">
                <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                    Missing MFA challenge context. Please start from the login screen again.
                </div>
                <NavLink
                    to={ROUTES.login}
                    className="text-blue-700 hover:text-blue-800 font-semibold dark:text-blue-300 dark:hover:text-blue-200 text-sm"
                >
                    Back to login
                </NavLink>
            </div>
        );
    }

    async function onSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setError("");
        if (!code.trim()) {
            setError("Enter the 6-digit code from your authenticator app.");
            return;
        }
        setBusy(true);
        try {
            const resp = await cognitoMfaVerify({
                email,
                session,
                code: code.trim(),
                friendly_name: "JobTracker",
            });
            if (resp.status === "OK") {
                handleSuccess(resp.tokens);
                return;
            }
            throw new Error("Verification requires an additional challenge. Please try logging in again.");
        } catch (err) {
            const msg = (err as { message?: string } | null)?.message ?? "Failed to verify code.";
            setError(msg);
            toast.error(msg, "MFA setup");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="space-y-5">
            <div className="text-sm text-slate-600 dark:text-slate-300">
                Step 2 of 2 — Add Job Applications Tracker to your authenticator app
            </div>

            {error && (
                <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
            )}

            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100">
                <ol className="list-decimal space-y-2 pl-5">
                    <li>Open your authenticator app (1Password, Authy, Google Authenticator, etc.).</li>
                    <li>Scan the QR code below, or enter the secret manually.</li>
                    <li>Enter the 6-digit code from the app to finish login.</li>
                </ol>
            </div>

            <div className="flex flex-col items-center gap-4 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
                {qrSrc ? (
                    <img src={qrSrc} alt="Authenticator QR code" className="h-48 w-48 border border-slate-200 dark:border-slate-800" />
                ) : (
                    <div className="text-sm text-slate-500 dark:text-slate-400">Generating QR code…</div>
                )}
                <div className="text-xs text-slate-500 dark:text-slate-400 break-all text-center">
                    Secret: <span className="font-mono">{secret || "••••••"}</span>
                </div>
                {otpauthUri && (
                    <a
                        href={otpauthUri}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200"
                        target="_blank"
                        rel="noreferrer"
                    >
                        Open in authenticator app
                    </a>
                )}
            </div>

            <form onSubmit={onSubmit} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Verification code</label>
                    <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        autoFocus
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
                    {busy ? "Verifying…" : "Verify & continue"}
                </button>
            </form>
        </div>
    );
}

