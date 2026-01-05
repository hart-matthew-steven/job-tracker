import { useCallback, useEffect, useState } from "react";
import { searchBoardJobs } from "../../api";
import type { JobBoardCard } from "../../types/api";
import { Loader2, Search } from "lucide-react";

type Props = {
    open: boolean;
    onClose: () => void;
    onSelect: (jobId: number) => void;
};

export function CommandMenu({ open, onClose, onSelect }: Props) {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<JobBoardCard[]>([]);
    const [loading, setLoading] = useState(false);

    const handleClose = useCallback(() => {
        setQuery("");
        setResults([]);
        setLoading(false);
        onClose();
    }, [onClose]);

    useEffect(() => {
        if (!open) return;
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") {
                handleClose();
            }
        }
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open, handleClose]);

    useEffect(() => {
        if (!open) return;
        const trimmed = query.trim();
        if (!trimmed) {
            return;
        }
        let cancelled = false;
        const handle = window.setTimeout(() => {
            setLoading(true);
            searchBoardJobs(trimmed)
                .then((data) => {
                    if (!cancelled) {
                        setResults(data.jobs);
                    }
                })
                .catch(() => {
                    if (!cancelled) {
                        setResults([]);
                    }
                })
                .finally(() => {
                    if (!cancelled) {
                        setLoading(false);
                    }
                });
        }, 200);
        return () => {
            cancelled = true;
            window.clearTimeout(handle);
        };
    }, [open, query]);

    useEffect(() => {
        if (open) return;
        const id = window.setTimeout(() => {
            setQuery("");
            setResults([]);
            setLoading(false);
        }, 0);
        return () => window.clearTimeout(id);
    }, [open]);

    if (!open) return null;

    function handleInputChange(value: string) {
        setQuery(value);
        if (!value.trim()) {
            setResults([]);
            setLoading(false);
        }
    }

    return (
        <div className="fixed inset-0 z-50">
            <div className="absolute inset-0 bg-black/60" onClick={handleClose} aria-hidden="true" />
            <div className="absolute inset-0 flex items-start justify-center p-6">
                <div className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950">
                    <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                        <Search size={18} className="text-slate-400" aria-hidden="true" />
                        <input
                            autoFocus
                            value={query}
                            onChange={(e) => handleInputChange(e.target.value)}
                            placeholder="Search companies, roles, or notes…"
                            className="flex-1 border-none bg-transparent text-base text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-slate-100"
                        />
                        <span className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-500 dark:border-slate-700">
                            Esc to close
                        </span>
                    </div>
            <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
                        {loading && (
                            <div className="flex items-center gap-2 text-sm text-slate-500">
                                <Loader2 className="h-4 w-4 animate-spin" /> Searching…
                            </div>
                        )}
                        {!loading && query && results.length === 0 && (
                            <p className="text-sm text-slate-500">No matches yet. Try a different keyword.</p>
                        )}
                        <ul className="space-y-2">
                            {results.map((result) => (
                                <li key={result.id}>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            onSelect(result.id);
                                            handleClose();
                                        }}
                                        className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-left text-sm transition hover:border-slate-400 hover:bg-slate-50 dark:border-slate-800 dark:hover:border-slate-600 dark:hover:bg-slate-900"
                                    >
                                        <p className="font-semibold text-slate-900 dark:text-slate-100">{result.company_name}</p>
                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                            {result.job_title} • {result.status.replace(/_/g, " ")}
                                        </p>
                                        {result.next_action_title && (
                                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                                Next: {result.next_action_title} · {result.next_action_at ? new Date(result.next_action_at).toLocaleDateString() : ""}
                                            </p>
                                        )}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    );
}

