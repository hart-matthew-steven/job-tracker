import { ArrowRight, CheckCircle, LayoutDashboard, Sparkles, Shield } from "lucide-react";
import { NavLink } from "react-router-dom";
import { ROUTES } from "../../routes/paths";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white text-slate-900 dark:from-slate-950 dark:to-slate-900 dark:text-slate-100">
      <header className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-6">
        <NavLink
          to={ROUTES.home}
          className="flex items-center gap-3 text-slate-900 dark:text-white cursor-pointer flex-shrink-0 min-w-[200px]"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white text-xl font-semibold dark:bg-slate-100 dark:text-slate-900">
            <span aria-hidden="true">💼</span>
          </div>
          <div className="text-lg font-semibold leading-tight text-slate-900 dark:text-white w-32 sm:w-auto">
            <span className="block whitespace-pre-line sm:hidden">{`Job\nApplications\nTracker`}</span>
            <span className="hidden sm:block whitespace-nowrap">Job Applications Tracker</span>
          </div>
        </NavLink>

        <div className="ml-auto flex flex-wrap items-center gap-3 text-sm">
          <NavLink to={ROUTES.login} className="text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300">
            Log in
          </NavLink>
          <NavLink
            to={ROUTES.register}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
          >
            Sign up
            <ArrowRight size={16} aria-hidden="true" />
          </NavLink>
        </div>
      </header>

      <main className="mx-auto mt-10 max-w-6xl px-6 pb-16">
        <section className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div>
            <h1 className="mt-4 text-4xl font-bold leading-tight tracking-tight text-slate-900 dark:text-white sm:text-5xl">
              A board-first workspace for job seekers who want enterprise-grade clarity.
            </h1>
            <p className="mt-6 text-lg text-slate-600 dark:text-slate-300">
              Replace spreadsheets and sticky notes with a drag-and-drop board, right-side insights, and dopamine-friendly
              focus tools. Designed for ambitious candidates shipping applications every week.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <NavLink
                to={ROUTES.register}
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
              >
                Start tracking
                <ArrowRight size={16} aria-hidden="true" />
              </NavLink>
              <NavLink
                to={ROUTES.demoBoard}
                className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-600 transition hover:border-slate-400 hover:text-slate-900 dark:border-slate-600 dark:text-slate-300 dark:hover:border-slate-400 dark:hover:text-slate-100"
              >
                View demo board
              </NavLink>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {[
                { title: "Momentum mode", body: "One-tap follow-ups, reminders, and activity pulse insights." },
                { title: "Secure by default", body: "Built on AWS Cognito + App Runner with guardrails baked in." },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                  <p className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    <CheckCircle size={16} className="text-emerald-500" aria-hidden="true" />
                    {item.title}
                  </p>
                  <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{item.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 -translate-y-6 translate-x-6 rounded-3xl bg-slate-200/40 blur-3xl dark:bg-slate-700/30" aria-hidden="true" />
            <div className="relative rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="border-b border-slate-200 px-6 py-4 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <div className="flex h-3 w-3 rounded-full bg-rose-400" />
                  <div className="flex h-3 w-3 rounded-full bg-amber-400" />
                  <div className="flex h-3 w-3 rounded-full bg-emerald-400" />
                </div>
              </div>
              <div className="space-y-4 px-6 py-6">
                <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                  <p className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">Board snapshot</p>
                  <p className="mt-2 text-2xl font-semibold">12 active applications</p>
                  <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-2xl bg-slate-100 p-3 dark:bg-slate-800">
                      <p className="text-xs text-slate-500">Interviews</p>
                      <p className="text-lg font-semibold">4</p>
                    </div>
                    <div className="rounded-2xl bg-slate-100 p-3 dark:bg-slate-800">
                      <p className="text-xs text-slate-500">Needs follow-up</p>
                      <p className="text-lg font-semibold text-amber-600">3</p>
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  Drag cards between stages, open drawers for context, and ship next actions without leaving the board.
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-16 grid gap-6 rounded-3xl border border-slate-200 bg-white px-6 py-8 dark:border-slate-800 dark:bg-slate-950 sm:grid-cols-3">
          {[
            { icon: LayoutDashboard, title: "Kanban-first", body: "Columns map to your funnel with drag-and-drop + keyboard shortcuts." },
            { icon: Sparkles, title: "Smart nudges", body: "Stale roles bubble up automatically so you can rescue momentum." },
            { icon: Shield, title: "Built for trust", body: "Cognito auth, document scanning, and email verification by default." },
          ].map((feature) => (
            <div key={feature.title} className="space-y-3">
              <feature.icon className="h-6 w-6 text-slate-900 dark:text-white" aria-hidden="true" />
              <p className="text-base font-semibold">{feature.title}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{feature.body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
        <p>© {new Date().getFullYear()} Job Applications Tracker. Built for operators on the hunt.</p>
      </footer>
    </div>
  );
}

