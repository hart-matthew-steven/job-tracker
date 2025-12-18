import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FormEvent } from "react";

import { useAuth } from "../../auth/AuthProvider";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { useSettings } from "../../hooks/useSettings";
import { changePassword } from "../../api";

type PageShellProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
};

function PageShell({ title, subtitle, children }: PageShellProps) {
    return (
        <div className="p-8">
            <div className="mb-6">
                <h1 className="text-3xl font-bold">{title}</h1>
                {subtitle && <p className="mt-1 text-slate-400">{subtitle}</p>}
            </div>
            {children}
        </div>
    );
}

export function ProfilePage() {
    const { user, loading, error, reload } = useCurrentUser();

    return (
        <PageShell title="Profile">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">User</div>

                {error && (
                    <div className="mt-4 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                        {error}
                        <div className="mt-2">
                            <button
                                type="button"
                                onClick={reload}
                                className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-900"
                            >
                                Retry
                            </button>
                        </div>
                    </div>
                )}

                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <div className="text-xs text-slate-500">Name</div>
                        <div className="mt-1 text-sm font-medium text-slate-100">
                            {loading ? "Loading…" : user?.name ?? "—"}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Email</div>
                        <div className="mt-1 text-sm font-medium text-slate-100">
                            {loading ? "Loading…" : user?.email ?? "—"}
                        </div>
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

export function SettingsPage() {
    const { settings, setAutoRefreshSeconds, loading, error } = useSettings();

    return (
        <PageShell title="Settings">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
                <label className="block text-sm font-medium text-slate-200">Auto refresh frequency</label>

                {error && (
                    <div className="mt-3 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                        {error}
                    </div>
                )}

                <div className="mt-2">
                    <select
                        value={settings.autoRefreshSeconds}
                        onChange={(e) => setAutoRefreshSeconds(Number(e.target.value))}
                        disabled={loading}
                        className="w-full max-w-xs rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
                    >
                        <option value={0}>Off (default)</option>
                        <option value={10}>10s</option>
                        <option value={30}>30s</option>
                        <option value={60}>60s</option>
                    </select>
                </div>
            </div>
        </PageShell>
    );
}

export function ChangePasswordPage() {
    const { logout } = useAuth();
    const nav = useNavigate();
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");

    const canSubmit = currentPassword.length > 0 && newPassword.length >= 8;
    const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;

    async function onSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setError("");
        setMessage("");

        if (!canSubmit) {
            setError("Please enter your current password and a new password (8+ characters).");
            return;
        }
        if (mismatch) {
            setError("New password and confirmation do not match.");
            return;
        }

        setBusy(true);
        try {
            const res = await changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            });
            setMessage(res?.message ?? "Password updated. Please log in again.");

            // Server revoked refresh tokens; we should also clear local auth and return to login.
            await logout();
            nav("/login", { replace: true });
        } catch (e2) {
            const err = e2 as { message?: string } | null;
            setError(err?.message ?? "Failed to change password");
        } finally {
            setBusy(false);
        }
    }

    return (
        <PageShell title="Change password" subtitle="This form validates locally and submits to the API.">
            {error && (
                <div className="mb-4 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                    {error}
                </div>
            )}
            {message && (
                <div className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3 text-sm text-slate-200">
                    {message}
                </div>
            )}

            <form onSubmit={onSubmit} className="max-w-lg space-y-4">
                <div>
                    <label className="block text-sm font-medium text-slate-200">Current password</label>
                    <input
                        type="password"
                        autoComplete="current-password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
                        placeholder="••••••••"
                        disabled={busy}
                        required
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-200">New password</label>
                    <input
                        type="password"
                        autoComplete="new-password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
                        placeholder="At least 8 characters"
                        disabled={busy}
                        required
                    />
                    <div className="mt-1 text-xs text-slate-500">Minimum length: 8 characters (local validation only).</div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-200">Confirm new password</label>
                    <input
                        type="password"
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className={[
                            "mt-1 w-full rounded-lg border bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2",
                            mismatch ? "border-red-900/60 focus:ring-red-900/30" : "border-slate-800 focus:ring-sky-600/30",
                        ].join(" ")}
                        placeholder="Re-enter new password"
                        disabled={busy}
                        required
                    />
                    {mismatch && <div className="mt-1 text-xs text-red-200">Passwords do not match.</div>}
                </div>

                <button
                    type="submit"
                    disabled={busy}
                    className={[
                        "rounded-lg px-4 py-2 text-sm font-semibold transition border",
                        busy
                            ? "cursor-not-allowed border-slate-800 bg-slate-900/40 text-slate-500"
                            : "border-slate-700 bg-slate-800/70 text-slate-100 hover:bg-slate-800",
                    ].join(" ")}
                >
                    {busy ? "Submitting…" : "Change password"}
                </button>
            </form>
        </PageShell>
    );
}


