import { useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import type { FormEvent } from "react";

import { cognitoRespondToChallenge } from "../../api/authCognito";
import { useAuth } from "../../auth/AuthProvider";
import { useToast } from "../../components/ui/toast";
import { ROUTES } from "../../routes/paths";
import type { CognitoTokens } from "../../types/api";

type ChallengeState = {
    email: string;
    session: string;
    next?: string;
};

export default function MfaChallengePage() {
    const { state } = useLocation();
    const nav = useNavigate();
    const toast = useToast();
    const { setSession } = useAuth();

    const ctx = (state as ChallengeState | null) ?? null;
    const [code, setCode] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    const email = ctx?.email ?? "";
    const session = ctx?.session ?? "";
    const next = ctx?.next ?? ROUTES.dashboard;

    function handleSuccess(tokens: CognitoTokens | null | undefined) {
        if (!tokens?.access_token) throw new Error("MFA challenge did not return an access token.");
        setSession(tokens);
        nav(next, { replace: true });
    }

    if (!email || !session) {
        return (
            <div className="space-y-4">
                <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                    Missing MFA challenge context. Please sign in again.
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
            const resp = await cognitoRespondToChallenge({
                email,
                challenge_name: "SOFTWARE_TOKEN_MFA",
                session,
                responses: {
                    USERNAME: email,
                    SOFTWARE_TOKEN_MFA_CODE: code.trim(),
                },
            });

            if (resp.status === "OK") {
                handleSuccess(resp.tokens);
                return;
            }

            throw new Error("Unexpected Cognito response. Please sign in again.");
        } catch (err) {
            const msg = (err as { message?: string } | null)?.message ?? "Invalid verification code.";
            setError(msg);
            toast.error(msg, "MFA");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="space-y-5">
            <div className="text-sm text-slate-600 dark:text-slate-300">Enter the code from your authenticator app</div>

            {error && (
                <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
            )}

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

            <div className="text-xs text-slate-500 dark:text-slate-400">
                Lost access to your authenticator app? Contact support so we can disable MFA on your account.
            </div>
        </div>
    );
}

