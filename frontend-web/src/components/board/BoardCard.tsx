import { useMemo } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CalendarDays, Clock, AlertTriangle, MapPin, Tag, Flag } from "lucide-react";
import type { JobBoardCard } from "../../types/api";

type Props = {
    card: JobBoardCard;
    columnId: string;
    onSelect: (card: JobBoardCard) => void;
};

const STATUS_ACCENTS: Record<string, string> = {
    applied: "bg-sky-500",
    recruiter_screen: "bg-blue-500",
    interviewing: "bg-indigo-500",
    onsite: "bg-purple-500",
    offer: "bg-amber-500",
    accepted: "bg-emerald-500",
    rejected: "bg-rose-500",
    withdrawn: "bg-stone-500",
    archived: "bg-slate-500",
};

const PRIORITY_BADGES: Record<string, string> = {
    high: "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
    normal: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200",
};

export function BoardCard({ card, columnId, onSelect }: Props) {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
        id: card.id,
        data: { type: "card", columnId },
    });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
    };

    const accent = STATUS_ACCENTS[card.status] ?? "bg-slate-400";
    const tags = useMemo(() => (card.tags || []).slice(0, 2), [card.tags]);
    const priority = (card.priority || "normal").toLowerCase();
    const priorityClass = PRIORITY_BADGES[priority] ?? PRIORITY_BADGES.normal;

    return (
        <div
            ref={setNodeRef}
            style={style}
            {...attributes}
            {...listeners}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(card)}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(card);
                }
            }}
            className={[
                "group rounded-2xl border p-4 text-left shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 cursor-grab active:cursor-grabbing",
                "border-slate-200 bg-white hover:border-sky-200 hover:shadow-md",
               "dark:border-slate-800 dark:bg-slate-900/70 dark:hover:border-sky-600/50",
                isDragging ? "opacity-80 ring-2 ring-sky-400" : "",
            ].join(" ")}
        >
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${accent}`} aria-hidden="true" />
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {card.status.replace(/_/g, " ")}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${priorityClass}`}>
                        <Flag size={10} aria-hidden="true" />
                        {priority}
                    </span>
                    {card.needs_follow_up && (
                        <div className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-semibold uppercase text-amber-900 dark:bg-amber-500/20 dark:text-amber-200 whitespace-nowrap">
                            <AlertTriangle size={10} aria-hidden="true" />
                            Follow up
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-3 space-y-1">
                <p className="font-semibold text-slate-900 dark:text-slate-100">{card.company_name}</p>
                <p className="text-sm text-slate-600 dark:text-slate-300">{card.job_title}</p>
                {card.location && (
                    <p className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                        <MapPin size={12} aria-hidden="true" />
                        {card.location}
                    </p>
                )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                {card.next_action_at && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        <Clock size={12} aria-hidden="true" />
                        {new Date(card.next_action_at).toLocaleDateString()}
                    </span>
                )}
                {card.last_action_at && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        <CalendarDays size={12} aria-hidden="true" />
                        {new Date(card.last_action_at).toLocaleDateString()}
                    </span>
                )}
                {tags.map((tag) => (
                    <span
                        key={tag}
                        className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    >
                        <Tag size={12} aria-hidden="true" />
                        {tag}
                    </span>
                ))}
            </div>
        </div>
    );
}


