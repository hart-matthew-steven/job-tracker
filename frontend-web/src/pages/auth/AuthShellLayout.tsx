// src/pages/auth/AuthShellLayout.tsx
import { Outlet } from "react-router-dom";

export default function AuthShellLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900/40">
        <div className="text-xl font-semibold">Job Tracker</div>
        <div className="text-sm text-slate-500 dark:text-slate-400 mt-1">Sign in to continue</div>
        <div className="mt-6">
          <Outlet />
        </div>
      </div>
    </div>
  );
}


