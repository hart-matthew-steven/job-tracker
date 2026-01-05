import { AlertTriangle, Filter } from "lucide-react";

type Props = {
    followUpsOnly: boolean;
    onToggleFollowUps: () => void;
};

export function BoardFilters({ followUpsOnly, onToggleFollowUps }: Props) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950/60">
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">
                <div className="inline-flex items-center gap-2">
                    <Filter size={12} aria-hidden="true" />
                    Filters
                </div>
                <button
                    type="button"
                    onClick={onToggleFollowUps}
                    className={[
                        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-semibold normal-case transition tracking-normal",
                        followUpsOnly
                            ? "border-amber-500 bg-amber-50 text-amber-900 dark:border-amber-400 dark:bg-amber-500/10 dark:text-amber-100"
                            : "border-slate-200 text-slate-600 hover:border-amber-300 hover:text-amber-700 dark:border-slate-700 dark:text-slate-300",
                    ].join(" ")}
                >
                    <AlertTriangle size={12} aria-hidden="true" />
                    Follow-ups
                </button>
            </div>
        </section>
    );
}

