import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FormEvent } from "react";

import { useAuth } from "../../auth/AuthProvider";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { useSettings } from "../../hooks/useSettings";
import { changePassword } from "../../api";
import { useToast } from "../../components/ui/ToastProvider";

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
                {subtitle && <p className="mt-1 text-slate-600 dark:text-slate-400">{subtitle}</p>}
            </div>
            {children}
        </div>
    );
}

export function ProfilePage() {
    const { user, loading, error, reload } = useCurrentUser();
  const toast = useToast();

    const lastErrorRef = useRef<string>("");
    useEffect(() => {
        if (!error) {
            lastErrorRef.current = "";
            return;
        }
        if (error === lastErrorRef.current) return;
        lastErrorRef.current = error;
        toast.error(error, "Profile");
    }, [error, toast]);

    return (
        <PageShell title="Profile">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900/50">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">User</div>

                {error && (
                    <div className="mt-4 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                        {error}
                        <div className="mt-2">
                            <button
                                type="button"
                                onClick={reload}
                                className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900"
                            >
                                Retry
                            </button>
                        </div>
                    </div>
                )}

                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <div className="text-xs text-slate-500">Name</div>
                        <div className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                            {loading ? "Loading…" : user?.name ?? "—"}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Email</div>
                        <div className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
                            {loading ? "Loading…" : user?.email ?? "—"}
                        </div>
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

export function SettingsPage() {
    const { settings, setAutoRefreshSeconds, setTheme, setDefaultJobsSort, setDefaultJobsView, setDataRetentionDays, loading, error } = useSettings();
  const toast = useToast();

    const lastErrorRef = useRef<string>("");
    useEffect(() => {
        if (!error) {
            lastErrorRef.current = "";
            return;
        }
        if (error === lastErrorRef.current) return;
        lastErrorRef.current = error;
        toast.error(error, "Settings");
    }, [error, toast]);

    return (
        <PageShell title="Settings">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900/50">
                <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Preferences</div>
                <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">Defaults for your Jobs workflow (stored in your account).</div>

                {error && (
                    <div className="mt-3 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
                        {error}
                    </div>
                )}

                <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/20">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Auto refresh frequency</label>
                        <div className="mt-2">
                            <select
                                value={settings.autoRefreshSeconds}
                                onChange={(e) => {
                                    const next = Number(e.target.value);
                                    void (async () => {
                                        try {
                                            await setAutoRefreshSeconds(next);
                                            toast.success("Settings saved.", "Settings");
                                        } catch {
                                            // error toast is handled by the `error` effect above
                                        }
                                    })();
                                }}
                                disabled={loading}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100"
                            >
                                <option value={0}>Off</option>
                                <option value={10}>10s</option>
                                <option value={30}>30s</option>
                                <option value={60}>60s</option>
                            </select>
                        </div>
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/20">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Appearance</label>
                        <div className="mt-2">
                            <select
                                value={settings.theme}
                                onChange={(e) => {
                                    const next = e.target.value;
                                    void (async () => {
                                        try {
                                            await setTheme(next);
                                            toast.success("Settings saved.", "Settings");
                                        } catch {}
                                    })();
                                }}
                                disabled={loading}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100"
                            >
                                <option value="dark">Dark</option>
                                <option value="light">Light</option>
                                <option value="system">System</option>
                            </select>
                        </div>
                        <div className="mt-2 text-xs text-slate-500">Theme applies app-wide (dark/light/system).</div>
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/20">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Jobs default sort</label>
                        <div className="mt-2">
                            <select
                                value={settings.defaultJobsSort}
                                onChange={(e) => {
                                    const next = e.target.value;
                                    void (async () => {
                                        try {
                                            await setDefaultJobsSort(next);
                                            toast.success("Settings saved.", "Settings");
                                        } catch {}
                                    })();
                                }}
                                disabled={loading}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100"
                            >
                                <option value="updated_desc">Updated (desc)</option>
                                <option value="company_asc">Company (A→Z)</option>
                                <option value="status_asc">Status</option>
                            </select>
                        </div>
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950/20">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Jobs default view</label>
                        <div className="mt-2">
                            <select
                                value={settings.defaultJobsView}
                                onChange={(e) => {
                                    const next = e.target.value;
                                    void (async () => {
                                        try {
                                            await setDefaultJobsView(next);
                                            toast.success("Settings saved.", "Settings");
                                        } catch {}
                                    })();
                                }}
                                disabled={loading}
                                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100"
                            >
                                <option value="all">All</option>
                                <option value="active">Active (not rejected)</option>
                                <option value="needs_followup">Needs follow-up (7d+)</option>
                            </select>
                        </div>
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 lg:col-span-2 dark:border-slate-800 dark:bg-slate-950/20">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Hide jobs after (days)</label>
                        <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                            This only hides jobs in the UI (Jobs + Dashboard). Data is still kept in the database.
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-3">
                            <input
                                type="number"
                                inputMode="numeric"
                                min={0}
                                step={1}
                                value={String(settings.dataRetentionDays ?? 0)}
                                onChange={(e) => {
                                    const next = Number(e.target.value);
                                    void (async () => {
                                        try {
                                            await setDataRetentionDays(next);
                                            toast.success("Settings saved.", "Settings");
                                        } catch {}
                                    })();
                                }}
                                disabled={loading}
                                className="w-40 rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100"
                                placeholder="0"
                                aria-label="Hide jobs after (days)"
                            />
                            <div className="text-xs text-slate-500">
                                0 = never hide. Examples: 365 = 1y, 730 = 2y.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

export function ChangePasswordPage() {
    const { logout } = useAuth();
    const nav = useNavigate();
  const toast = useToast();
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
            const msg = "Please enter your current password and a new password (8+ characters).";
            setError(msg);
            toast.error(msg, "Change password");
            return;
        }
        if (mismatch) {
            const msg = "New password and confirmation do not match.";
            setError(msg);
            toast.error(msg, "Change password");
            return;
        }

        setBusy(true);
        try {
            const res = await changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            });
            const msg = res?.message ?? "Password updated. Please log in again.";
            setMessage(msg);
            toast.success(msg, "Change password");

            // Server revoked refresh tokens; we should also clear local auth and return to login.
            await logout();
            nav("/login", { replace: true });
        } catch (e2) {
            const err = e2 as { message?: string } | null;
            const msg = err?.message ?? "Failed to change password";
            setError(msg);
            toast.error(msg, "Change password");
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
                <div className="mb-4 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-200">
                    {message}
                </div>
            )}

            <form onSubmit={onSubmit} className="max-w-lg space-y-4">
                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Current password</label>
                    <input
                        type="password"
                        autoComplete="current-password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500"
                        placeholder="••••••••"
                        disabled={busy}
                        required
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">New password</label>
                    <input
                        type="password"
                        autoComplete="new-password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-800 dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500"
                        placeholder="At least 8 characters"
                        disabled={busy}
                        required
                    />
                    <div className="mt-1 text-xs text-slate-500">Minimum length: 8 characters (local validation only).</div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Confirm new password</label>
                    <input
                        type="password"
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className={[
                            "mt-1 w-full rounded-lg border px-3 py-2 placeholder:text-slate-400 focus:outline-none focus:ring-2",
                            "bg-white text-slate-900 border-slate-300 focus:ring-sky-600/30",
                            "dark:bg-slate-950/40 dark:text-slate-100 dark:placeholder:text-slate-500 dark:border-slate-800 dark:focus:ring-sky-600/30",
                            mismatch ? "border-red-500 focus:ring-red-500/30 dark:border-red-900/60 dark:focus:ring-red-900/30" : "",
                        ].join(" ")}
                        placeholder="Re-enter new password"
                        disabled={busy}
                        required
                    />
                    {mismatch && <div className="mt-1 text-xs text-red-600 dark:text-red-200">Passwords do not match.</div>}
                </div>

                <button
                    type="submit"
                    disabled={busy}
                    className={[
                        "rounded-lg px-4 py-2 text-sm font-semibold transition border",
                        busy
                            ? "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500"
                            : "border-slate-300 bg-slate-900 text-white hover:bg-slate-800 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800",
                    ].join(" ")}
                >
                    {busy ? "Submitting…" : "Change password"}
                </button>
            </form>
        </PageShell>
    );
}


