import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { KanbanSquare, BarChart3, LogOut, Search, Menu, Plus, Sparkles } from "lucide-react";
import { useCurrentUser } from "../../hooks/useCurrentUser";
import { CurrentUserProvider } from "../../context/CurrentUserContext";
import { CreditsProvider } from "../../context/CreditsContext";
import { ROUTES } from "../../routes/paths";
import type { ActivityMetrics, UserMeOut } from "../../types/api";
import { getActivityPulse } from "../../api";
import { CommandMenu } from "../search/CommandMenu";
import CreditsBadge from "./CreditsBadge";

function cx(...parts: Array<string | false | null | undefined>) {
    return parts.filter(Boolean).join(" ");
}

type AccountMenuProps = { onLogout: () => void; user: UserMeOut | null; isStub: boolean };

function AccountMenu({ onLogout, user, isStub }: AccountMenuProps) {
    const [open, setOpen] = useState(false);
    const buttonRef = useRef<HTMLButtonElement | null>(null);
    const panelRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!open) return;
        function onDocClick(e: MouseEvent) {
            const btn = buttonRef.current;
            const panel = panelRef.current;
            if (!btn || !panel) return;
            const target = e.target as Node | null;
            if (!target) return;
            if (btn.contains(target) || panel.contains(target)) return;
            setOpen(false);
        }
        function onKeyDown(e: KeyboardEvent) {
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
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-white hover:text-slate-900 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-white"
                aria-haspopup="menu"
                aria-expanded={open}
            >
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" aria-hidden="true">
                    {String(user?.name || user?.email || "A")
                        .trim()
                        .split(/\s+/)
                        .slice(0, 2)
                        .map((p) => p[0]?.toUpperCase())
                        .join("")}
                </span>
                <span className="hidden sm:block">{user?.name ?? "Account"}</span>
            </button>

            {open && (
                <div
                    ref={panelRef}
                    role="menu"
                    aria-label="Account"
                    className="absolute right-0 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-950"
                >
                    <div className="px-4 py-3">
                        <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{user?.name ?? "Account"}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{user?.email ?? ""}</p>
                        {isStub && <p className="mt-2 text-xs text-amber-500">Demo mode</p>}
                    </div>
                    <div className="border-t border-slate-200 dark:border-slate-800">
                        <NavLink
                            to={ROUTES.profile}
                            onClick={() => setOpen(false)}
                            role="menuitem"
                            className="block px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/60"
                        >
                            Profile
                        </NavLink>
                        <NavLink
                            to={ROUTES.settings}
                            onClick={() => setOpen(false)}
                            role="menuitem"
                            className="block px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/60"
                        >
                            Settings
                        </NavLink>
                        <NavLink
                            to={ROUTES.billing}
                            onClick={() => setOpen(false)}
                            role="menuitem"
                            className="block px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/60"
                        >
                            Billing
                        </NavLink>
                        <NavLink
                            to={ROUTES.changePassword}
                            onClick={() => setOpen(false)}
                            role="menuitem"
                            className="block px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/60"
                        >
                            Change password
                        </NavLink>
                    </div>
                    <div className="border-t border-slate-200 p-3 dark:border-slate-800">
                        <button
                            type="button"
                            onClick={() => {
                                setOpen(false);
                                onLogout();
                            }}
                            role="menuitem"
                            className="flex w-full items-center justify-center gap-2 rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
                        >
                            <LogOut size={16} aria-hidden="true" />
                            Logout
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

const NAV_ITEMS = [
    { to: ROUTES.board, label: "Board", icon: KanbanSquare },
    { to: ROUTES.insights, label: "Insights", icon: BarChart3 },
    { to: ROUTES.aiAssistant, label: "AI Assistant", icon: Sparkles },
];

export type ShellContext = {
    openCommandMenu: () => void;
    pulse: ActivityMetrics | null;
    refreshPulse: () => void;
};

type Props = { onLogout?: () => void | Promise<void> };

export default function AppShell({ onLogout }: Props) {
    const currentUser = useCurrentUser();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [logoutBusy, setLogoutBusy] = useState(false);
    const [commandOpen, setCommandOpen] = useState(false);
    const [pulse, setPulse] = useState<ActivityMetrics | null>(null);
    const nav = useNavigate();
    const location = useLocation();
    const mustChangePassword = !!currentUser.user?.must_change_password;
    const shouldForcePasswordChange = !currentUser.loading && mustChangePassword && location.pathname !== ROUTES.changePassword;

    const refreshPulse = useCallback(() => {
        getActivityPulse()
            .then(setPulse)
            .catch(() => null);
    }, []);

    useEffect(() => {
        refreshPulse();
    }, [refreshPulse]);

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setCommandOpen(true);
            }
        }
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, []);

    const shellContext: ShellContext = useMemo(
        () => ({
            openCommandMenu: () => setCommandOpen(true),
            pulse,
            refreshPulse,
        }),
        [pulse, refreshPulse]
    );

    const handleGlobalCreateJob = useCallback(() => {
        setMobileOpen(false);
        nav(`${ROUTES.board}?create=1`);
    }, [nav]);

    if (shouldForcePasswordChange) {
        return <Navigate to={ROUTES.changePassword} replace />;
    }

    async function handleLogout() {
        if (logoutBusy) return;
        setLogoutBusy(true);
        try {
            await onLogout?.();
        } finally {
            setMobileOpen(false);
            nav(ROUTES.home, { replace: true });
            setLogoutBusy(false);
        }
    }

    const homeTarget = currentUser.user ? ROUTES.board : ROUTES.home;

    return (
    <CurrentUserProvider value={currentUser}>
        <CreditsProvider>
            <div className="flex min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
                <aside className="hidden w-20 flex-col border-r border-slate-200 bg-white/80 pt-6 dark:border-slate-800 dark:bg-slate-950 md:flex">
                    <div className="flex flex-col items-center gap-8">
                        <NavLink
                            to={homeTarget}
                            aria-label="Home"
                            className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white text-xl font-semibold dark:bg-slate-100 dark:text-slate-900 cursor-pointer"
                        >
                            <span aria-hidden="true">💼</span>
                        </NavLink>
                        <nav className="flex flex-col gap-4">
                            {NAV_ITEMS.map((item) => (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    aria-label={item.label}
                                    title={item.label}
                                    className={({ isActive }) =>
                                        cx(
                                            "group relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition",
                                            isActive
                                                ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                                                : "border-transparent text-slate-400 hover:border-slate-300 hover:text-slate-900 dark:text-slate-500 dark:hover:text-slate-100"
                                        )
                                    }
                                >
                                    <item.icon size={18} />
                                    <span className="pointer-events-none absolute left-12 rounded-full bg-slate-900 px-2 py-1 text-xs text-white opacity-0 transition group-hover:opacity-100 dark:bg-slate-100 dark:text-slate-900">
                                        {item.label}
                                    </span>
                                </NavLink>
                            ))}
                        </nav>
                    </div>
                </aside>

                <div className="flex flex-1 flex-col">
                    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950">
                        <div className="flex h-16 items-center justify-between px-4">
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-slate-800 dark:text-slate-200 md:hidden"
                                    onClick={() => setMobileOpen(true)}
                                    aria-label="Open navigation"
                                >
                                    <Menu size={16} />
                                </button>
                                <NavLink
                                    to={homeTarget}
                                    className="hidden cursor-pointer text-sm font-semibold uppercase tracking-[0.4em] text-slate-400 dark:text-slate-500 md:block"
                                >
                                    Job Applications Tracker
                                </NavLink>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="hidden md:block">
                                    <button
                                        type="button"
                                        onClick={() => setCommandOpen(true)}
                                        className="items-center gap-2 rounded-full border border-slate-200 px-3 py-2 text-sm text-slate-500 hover:border-slate-300 hover:text-slate-900 dark:border-slate-800 dark:text-slate-300 md:flex md:w-60 lg:w-72 xl:w-80"
                                    >
                                        <span className="inline-flex items-center gap-2 text-slate-500 dark:text-slate-300">
                                            <Search size={16} aria-hidden="true" />
                                            <span className="truncate">Search…</span>
                                        </span>
                                        <kbd className="ml-auto rounded border border-slate-300 px-1 text-xs">⌘K</kbd>
                                    </button>
                                </div>
                                <CreditsBadge className="hidden md:inline-flex" />
                                <div className="flex items-center gap-2 md:hidden">
                                    <button
                                        type="button"
                                        onClick={() => setCommandOpen(true)}
                                        className="inline-flex flex-1 items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-2 text-sm text-slate-500 shadow-sm hover:border-slate-300 hover:bg-white hover:text-slate-900 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-300 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                                    >
                                        <Search size={16} aria-hidden="true" />
                                        <span className="truncate">Search…</span>
                                    </button>
                                    <CreditsBadge />
                                    <button
                                        type="button"
                                        onClick={handleGlobalCreateJob}
                                        className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                                    >
                                        <Plus size={16} aria-hidden="true" />
                                        <span>Create</span>
                                    </button>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleGlobalCreateJob}
                                    className="hidden items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white sm:inline-flex"
                                >
                                    <Plus size={16} aria-hidden="true" />
                                    Create job
                                </button>
                                <AccountMenu onLogout={() => void handleLogout()} user={currentUser.user} isStub={currentUser.isStub} />
                            </div>
                        </div>
                    </header>

                    <main className="flex-1 overflow-y-auto px-4 py-6 lg:px-8">
                        <Outlet context={shellContext} />
                    </main>
                </div>

                {mobileOpen && (
                    <>
                        <div className="fixed inset-0 z-40 bg-black/50" onClick={() => setMobileOpen(false)} aria-hidden="true" />
                        <div className="fixed inset-y-0 left-0 z-50 w-72 bg-white p-6 dark:bg-slate-950">
                            <nav className="space-y-4">
                                {NAV_ITEMS.map((item) => (
                                    <NavLink
                                        key={item.to}
                                        to={item.to}
                                        onClick={() => setMobileOpen(false)}
                                        className={({ isActive }) =>
                                            cx(
                                                "flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-semibold",
                                                isActive ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "text-slate-600 dark:text-slate-300"
                                            )
                                        }
                                    >
                                        <item.icon size={18} />
                                        {item.label}
                                    </NavLink>
                                ))}
                            </nav>
                        </div>
                    </>
                )}
            </div>

            <CommandMenu
                open={commandOpen}
                onClose={() => setCommandOpen(false)}
                onSelect={(jobId) => {
                    setCommandOpen(false);
                    nav(`${ROUTES.board}?jobId=${jobId}`);
                }}
            />
        </CreditsProvider>
        </CurrentUserProvider>
    );
}

