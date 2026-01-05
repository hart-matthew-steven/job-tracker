import { useDroppable } from "@dnd-kit/core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { JobBoardCard } from "../../types/api";
import { BoardCard } from "./BoardCard";

const COLUMN_PAGE_SIZE = 25;
const LIST_MAX_HEIGHT = "calc(100vh - 320px)";

type Props = {
    status: string;
    title: string;
    jobs: JobBoardCard[];
    totalCount: number;
    onSelect: (card: JobBoardCard) => void;
    highlight?: boolean;
};

export function BoardColumn({ status, title, jobs, totalCount, onSelect, highlight = false }: Props) {
    const { isOver, setNodeRef } = useDroppable({
        id: `column-${status}`,
        data: { type: "column", columnId: status },
    });

    const showTotal = jobs.length !== totalCount;

    const [visibleCount, setVisibleCount] = useState(COLUMN_PAGE_SIZE);
    const listRef = useRef<HTMLDivElement | null>(null);
    const clampedVisibleCount = Math.min(visibleCount, jobs.length);
    const hasMore = clampedVisibleCount < jobs.length;

    useEffect(() => {
        if (listRef.current) {
            listRef.current.scrollTop = 0;
        }
    }, [jobs]);

    const handleScroll = useCallback(() => {
        const node = listRef.current;
        if (!node || !hasMore) return;
        const { scrollTop, scrollHeight, clientHeight } = node;
        if (scrollTop + clientHeight >= scrollHeight - 16) {
            setVisibleCount((prev) => Math.min(prev + COLUMN_PAGE_SIZE, jobs.length));
        }
    }, [hasMore, jobs.length]);

    const visibleJobs = useMemo(() => jobs.slice(0, clampedVisibleCount), [jobs, clampedVisibleCount]);

    const containerClass = [
        "flex h-full flex-col gap-3 rounded-3xl border border-slate-200 bg-white/70 p-4 transition dark:border-slate-800 dark:bg-slate-900/40",
        (isOver || highlight) && "ring-2 ring-sky-400 dark:ring-sky-500",
    ]
        .filter(Boolean)
        .join(" ");

    return (
        <div
            ref={setNodeRef}
            className={containerClass}
        >
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">{title}</p>
                    <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{jobs.length}</p>
                </div>
                <div className="text-xs font-semibold text-slate-400 dark:text-slate-500">
                    {showTotal ? `${jobs.length}/${totalCount}` : `${totalCount} cards`}
                </div>
            </div>
            <div
                ref={listRef}
                onScroll={handleScroll}
                style={{ maxHeight: LIST_MAX_HEIGHT }}
                className="flex-1 space-y-3 overflow-y-auto pb-4"
            >
                <SortableContext items={visibleJobs.map((job) => job.id)} strategy={verticalListSortingStrategy}>
                    {visibleJobs.length === 0 && (
                        <div className="rounded-xl border border-dashed border-slate-300 p-4 text-center text-xs text-slate-400 dark:border-slate-700 dark:text-slate-500 cursor-copy">
                            Drop a role here
                        </div>
                    )}
                    {visibleJobs.map((job) => (
                        <BoardCard key={job.id} card={job} columnId={status} onSelect={onSelect} />
                    ))}
                    {hasMore && (
                        <div className="rounded-xl border border-dashed border-slate-300 bg-white/40 px-3 py-2 text-center text-[11px] text-slate-400 dark:border-slate-700 dark:bg-slate-900/30 dark:text-slate-500">
                            Showing {visibleJobs.length} of {jobs.length}. Keep scrolling…
                        </div>
                    )}
                </SortableContext>
            </div>
        </div>
    );
}

