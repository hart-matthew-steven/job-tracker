import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useCurrentUser } from "../../hooks/useCurrentUser";

function cx(...parts) {
    return parts.filter(Boolean).join(" ");
}

function AppNavLink({ to, children, onNavigate }) {
    return (
        <NavLink
            to={to}
            end
            onClick={onNavigate}
            className={({ isActive }) =>
                cx(
                    "block rounded-md px-3 py-2 text-sm font-medium transition",
                    isActive
                        ? "bg-slate-900 text-slate-50"
                        : "text-slate-300 hover:bg-slate-900/60 hover:text-slate-50"
                )
            }
        >
            {children}
        </NavLink>
    );
}

function AccountMenu({ onLogout }) {
    const { user, isStub } = useCurrentUser();
    const [open, setOpen] = useState(false);
    const buttonRef = useRef(null);
    const panelRef = useRef(null);

    useEffect(() => {
        if (!open) return;
        function onDocClick(e) {
            const btn = buttonRef.current;
            const panel = panelRef.current;
            if (!btn || !panel) return;
            if (btn.contains(e.target) || panel.contains(e.target)) return;
            setOpen(false);
        }
        function onKeyDown(e) {
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("mousedown", onDocClick);
        document.addEventListener("keydown", onKeyDown);
        return () => {
            document.removeEventListener("mousedown", onDocClick);
            document.removeEventListener("keydown", onKeyDown);
        };
    }, [open]);

    return (
        <div className="relative">
            <button
                ref={buttonRef}
                type="button"
                onClick={() => setOpen((v) => !v)}
                className={cx(
                    "inline-flex items-center gap-2 rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm",
                    "text-slate-200 hover:bg-slate-900/60 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
                )}
                aria-haspopup="menu"
                aria-expanded={open}
            >
                <span
                    className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-slate-100 text-xs font-semibold"
                    aria-hidden="true"
                >
                    {String(user?.name || user?.email || "A")
                        .trim()
                        .split(/\s+/)
                        .slice(0, 2)
                        .map((p) => p[0]?.toUpperCase())
                        .join("")}
                </span>
                <span className="hidden sm:block font-medium">{user?.name ?? "Account"}</span>
                <span className="text-slate-400" aria-hidden="true">
                    ▾
                </span>
            </button>

            {open && (
                <div
                    ref={panelRef}
                    role="menu"
                    aria-label="Account"
                    className={cx(
                        "absolute right-0 mt-2 w-64 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-sm",
                        "z-50"
                    )}
                >
                    <div className="px-4 py-3">
                        <div className="text-sm font-semibold text-slate-100">{user?.name ?? "Account"}</div>
                        <div className="text-sm text-slate-400">{user?.email ?? ""}</div>
                        {isStub && <div className="mt-2 text-xs text-slate-500">Stub user (API later)</div>}
                    </div>

                    <div className="border-t border-slate-800">
                        <NavLink
                            to="/profile"
                            onClick={() => setOpen(false)}
                            className="block px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-900/60"
                            role="menuitem"
                        >
                            Profile <span className="text-xs text-slate-500">(stub)</span>
                        </NavLink>
                        <NavLink
                            to="/settings"
                            onClick={() => setOpen(false)}
                            className="block px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-900/60"
                            role="menuitem"
                        >
                            Settings <span className="text-xs text-slate-500">(local)</span>
                        </NavLink>
                        <NavLink
                            to="/change-password"
                            onClick={() => setOpen(false)}
                            className="block px-4 py-2 text-left text-sm text-slate-200 hover:bg-slate-900/60"
                            role="menuitem"
                        >
                            Change password <span className="text-xs text-slate-500">(stub)</span>
                        </NavLink>
                    </div>

                    <div className="border-t border-slate-800 p-2">
                        <button
                            type="button"
                            onClick={() => {
                                setOpen(false);
                                onLogout();
                            }}
                            className={cx(
                                "w-full rounded-md px-3 py-2 text-sm font-medium",
                                "bg-slate-800 text-slate-100 hover:bg-slate-700"
                            )}
                            role="menuitem"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default function AppShell({ onLogout }) {
    const { user, isStub } = useCurrentUser();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [logoutBusy, setLogoutBusy] = useState(false);
    const nav = useNavigate();

    async function handleLogout() {
        if (logoutBusy) return;
        setLogoutBusy(true);
        try {
            await onLogout?.();
        } finally {
            setMobileOpen(false);
            nav("/login", { replace: true });
            setLogoutBusy(false);
        }
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            {/* Top bar */}
            <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950">
                <div className="mx-auto max-w-6xl px-4">
                    <div className="flex h-14 items-center justify-between">
                        <div className="flex items-center gap-3">
                            <button
                                type="button"
                                className={cx(
                                    "md:hidden inline-flex items-center justify-center rounded-md",
                                    "border border-slate-800 bg-slate-950 px-2.5 py-2",
                                    "text-slate-200 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
                                )}
                                onClick={() => setMobileOpen(true)}
                                aria-label="Open navigation"
                            >
                                <span aria-hidden="true">☰</span>
                            </button>

                            <NavLink to="/" className="flex items-center gap-2" aria-label="Go to dashboard">
                                <div
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-slate-800 text-slate-100 text-sm font-semibold"
                                    aria-hidden="true"
                                >
                                    JT
                                </div>
                                <div className="font-semibold tracking-tight text-slate-100 hover:text-white">
                                    Job Tracker
                                </div>
                            </NavLink>
                        </div>

                        <div className="flex items-center gap-3">
                            <AccountMenu onLogout={handleLogout} />
                        </div>
                    </div>
                </div>
            </header>

            <div className="mx-auto max-w-6xl px-4">
                <div className="flex">
                    {/* Desktop sidebar */}
                    <aside className="hidden md:block w-56 py-6 pr-6">
                        <nav className="space-y-1">
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                Navigation
                            </div>
                            <AppNavLink to="/">Dashboard</AppNavLink>
                            <AppNavLink to="/jobs">Jobs</AppNavLink>
                        </nav>
                    </aside>

                    {/* Main */}
                    <main className="flex-1 py-6">
                        <Outlet />
                    </main>
                </div>
            </div>

            {/* Mobile drawer */}
            {mobileOpen && (
                <>
                    <div
                        className="fixed inset-0 z-40 bg-black/60"
                        onClick={() => setMobileOpen(false)}
                        aria-hidden="true"
                    />
                    <aside className="fixed inset-y-0 left-0 z-50 w-80 bg-slate-950 border-r border-slate-800">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
                            <div className="font-semibold">Job Tracker</div>
                            <button
                                type="button"
                                className="rounded-md border border-slate-800 bg-slate-950 px-2.5 py-2 text-slate-200 hover:bg-slate-900"
                                onClick={() => setMobileOpen(false)}
                                aria-label="Close navigation"
                            >
                                <span aria-hidden="true">✕</span>
                            </button>
                        </div>
                        <div className="p-4">
                            <nav className="space-y-1">
                                <AppNavLink to="/" onNavigate={() => setMobileOpen(false)}>
                                    Dashboard
                                </AppNavLink>
                                <AppNavLink to="/jobs" onNavigate={() => setMobileOpen(false)}>
                                    Jobs
                                </AppNavLink>
                            </nav>

                            <div className="mt-6 rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                    Account
                                </div>
                                <div className="mt-2 text-sm font-medium text-slate-100">
                                    {user?.name ?? "Account"}
                                </div>
                                <div className="text-sm text-slate-400">{user?.email ?? ""}</div>
                                {isStub && (
                                    <div className="mt-2 text-xs text-slate-500">Stub user (API later)</div>
                                )}
                                <div className="mt-3">
                                    <button
                                        type="button"
                                        onClick={() => {
                                            handleLogout();
                                        }}
                                        disabled={logoutBusy}
                                        className={[
                                            "w-full rounded-md px-3 py-2 text-sm font-medium transition",
                                            logoutBusy
                                                ? "cursor-not-allowed bg-slate-900/40 text-slate-500"
                                                : "bg-slate-800 text-slate-100 hover:bg-slate-700",
                                        ].join(" ")}
                                    >
                                        {logoutBusy ? "Logging out…" : "Logout"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </aside>
                </>
            )}
        </div>
    );
}


