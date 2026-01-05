import { RefreshCcw } from "lucide-react";

type Props = {
  isRefreshing: boolean;
  onRefresh: () => void;
};

export function BoardHeader({ isRefreshing, onRefresh }: Props) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">Board</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-900 dark:text-slate-100">Pipeline overview</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Drag roles across stages, keep momentum, and never miss a follow-up.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white/70 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-400 hover:bg-white hover:text-slate-900 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200 dark:hover:border-slate-500 dark:hover:bg-slate-700"
        >
          <RefreshCcw size={16} className={isRefreshing ? "animate-spin" : ""} aria-hidden="true" />
          Refresh board
        </button>
      </div>
    </div>
  );
}

