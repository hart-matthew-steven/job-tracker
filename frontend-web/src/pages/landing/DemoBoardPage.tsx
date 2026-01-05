import { useCallback, useMemo, useState } from "react";
import {
    DndContext,
    DragEndEvent,
    DragOverEvent,
    DragStartEvent,
    KeyboardSensor,
    PointerSensor,
    closestCorners,
    useSensor,
    useSensors,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { NavLink } from "react-router-dom";
import type { JobBoardCard } from "../../types/api";
import { ROUTES } from "../../routes/paths";
import { BoardColumn } from "../../components/board/BoardColumn";
import { DemoBoardDrawer } from "./DemoBoardDrawer";
import { createDemoData, type DemoJobDetail } from "./demoBoardData";

type BoardColumnGroup = {
    id: string;
    label: string;
    statuses: string[];
    defaultStatus?: string;
};

const BASE_COLUMN_GROUPS: BoardColumnGroup[] = [
    { id: "applied", label: "Applied", statuses: ["applied"], defaultStatus: "applied" },
    {
        id: "interviewing",
        label: "Interviewing",
        statuses: ["recruiter_screen", "interviewing", "onsite"],
        defaultStatus: "interviewing",
    },
    { id: "offer", label: "Offer", statuses: ["offer"], defaultStatus: "offer" },
    {
        id: "closed",
        label: "Closed",
        statuses: ["accepted", "rejected", "withdrawn", "archived"],
        defaultStatus: "rejected",
    },
];

function formatStatusLabel(status: string): string {
    return status
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export default function DemoBoardPage() {
    const demoData = useMemo(() => createDemoData(), []);
    const [cards, setCards] = useState<JobBoardCard[]>(demoData.cards);
    const [details, setDetails] = useState<Record<number, DemoJobDetail>>(demoData.details);
    const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
    const [activeDropColumn, setActiveDropColumn] = useState<string | null>(null);
    const statuses = demoData.statuses;

    const columnConfigs = useMemo(() => {
        const configs: BoardColumnGroup[] = BASE_COLUMN_GROUPS.map((group) => ({ ...group }));
        const knownStatuses = new Set(configs.flatMap((group) => group.statuses));
        statuses.forEach((status) => {
            if (!knownStatuses.has(status)) {
                configs.push({
                    id: status,
                    label: formatStatusLabel(status),
                    statuses: [status],
                    defaultStatus: status,
                });
                knownStatuses.add(status);
            }
        });
        return configs;
    }, [statuses]);

    const statusToColumnId = useMemo(() => {
        const map = new Map<string, string>();
        columnConfigs.forEach((column) => {
            column.statuses.forEach((status) => map.set(status, column.id));
        });
        return map;
    }, [columnConfigs]);

    const columnDefaultStatus = useMemo(() => {
        const map = new Map<string, string>();
        columnConfigs.forEach((column) => {
            map.set(column.id, column.defaultStatus ?? column.statuses[0] ?? column.id);
        });
        return map;
    }, [columnConfigs]);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const grouped = useMemo(() => {
        const map = new Map<string, JobBoardCard[]>();
        columnConfigs.forEach((column) => map.set(column.id, []));
        cards.forEach((card) => {
            const columnId = statusToColumnId.get(card.status) ?? card.status;
            if (!map.has(columnId)) {
                map.set(columnId, []);
            }
            map.get(columnId)!.push(card);
        });
        return map;
    }, [cards, columnConfigs, statusToColumnId]);

    const totalsByColumn = useMemo(() => {
        const counts = new Map<string, number>();
        columnConfigs.forEach((column) => counts.set(column.id, 0));
        cards.forEach((card) => {
            const columnId = statusToColumnId.get(card.status) ?? card.status;
            counts.set(columnId, (counts.get(columnId) ?? 0) + 1);
        });
        return counts;
    }, [cards, columnConfigs, statusToColumnId]);

    const selectedJob = selectedJobId ? cards.find((card) => card.id === selectedJobId) ?? null : null;
    const selectedDetail = selectedJobId ? details[selectedJobId] : undefined;

    const resolveColumnFromOver = useCallback((over: DragOverEvent["over"]) => {
        if (!over) return null;
        const data = (over.data?.current as { columnId?: string } | undefined) ?? undefined;
        if (data?.columnId) return data.columnId;
        if (typeof over.id === "string" && over.id.startsWith("column-")) {
            return over.id.replace("column-", "");
        }
        return null;
    }, []);

    const handleDragStart = useCallback((event: DragStartEvent) => {
        const columnId = event.active.data.current?.columnId as string | undefined;
        if (columnId) setActiveDropColumn(columnId);
    }, []);

    const handleDragOver = useCallback(
        (event: DragOverEvent) => {
            const columnId = resolveColumnFromOver(event.over);
            if (columnId) setActiveDropColumn(columnId);
        },
        [resolveColumnFromOver]
    );

    const handleDragEnd = useCallback(
        (event: DragEndEvent) => {
            setActiveDropColumn(null);
            const { active, over } = event;
            if (!active || !over) return;
            const jobId = Number(active.id);
            const sourceColumnId = active.data.current?.columnId as string | undefined;
            const targetColumnId = resolveColumnFromOver(over);
            if (!jobId || !sourceColumnId || !targetColumnId || sourceColumnId === targetColumnId) return;
            const nextStatus = columnDefaultStatus.get(targetColumnId) ?? targetColumnId;
            setCards((prev) => prev.map((card) => (card.id === jobId ? { ...card, status: nextStatus } : card)));
        },
        [columnDefaultStatus, resolveColumnFromOver]
    );

    const handleStatusChange = useCallback((jobId: number, status: string) => {
        setCards((prev) => prev.map((card) => (card.id === jobId ? { ...card, status } : card)));
    }, []);

    const handleMomentumUpdate = useCallback((jobId: number, update: { last_action_at?: string | null; next_action_at?: string | null; next_action_title?: string | null }) => {
        setCards((prev) =>
            prev.map((card) =>
                card.id === jobId
                    ? {
                        ...card,
                        last_action_at: update.last_action_at ?? card.last_action_at,
                        next_action_at: update.next_action_at ?? card.next_action_at,
                        next_action_title: update.next_action_title ?? card.next_action_title,
                        needs_follow_up: false,
                    }
                    : card
            )
        );
    }, []);

    const handleDetailUpdate = useCallback((detail: DemoJobDetail) => {
        setDetails((prev) => ({ ...prev, [detail.id]: detail }));
    }, []);

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
                    <NavLink to={ROUTES.login} className="text-sm font-medium text-slate-600 transition hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100">
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

            <main className="mx-auto max-w-6xl px-6 pb-16">
                <section className="mt-10 space-y-6">
                    <div className="space-y-4">
                        <p className="text-sm uppercase tracking-[0.4em] text-slate-400 dark:text-slate-500">Live demo</p>
                        <h1 className="text-4xl font-bold leading-tight text-slate-900 dark:text-white sm:text-5xl">
                            Explore the drag-and-drop board without an account.
                        </h1>
                        <p className="text-lg text-slate-600 dark:text-slate-300">
                            This sandbox mirrors the in-app experience—columns, smart nudges, the right-side drawer, and timeline activity—so your team can feel the flow before creating an account.
                        </p>
                    </div>

                    <div className="rounded-[34px] border border-slate-200 bg-white/80 p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900/60">
                        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">Board snapshot</p>
                                <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{cards.length} active applications</p>
                            </div>
                            <div className="flex gap-2 text-sm text-slate-500 dark:text-slate-400">
                                <span className="rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                                    No login required
                                </span>
                                <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                    Sample data preview
                                </span>
                            </div>
                        </div>

                        <DndContext
                            sensors={sensors}
                            collisionDetection={closestCorners}
                            onDragStart={handleDragStart}
                            onDragOver={handleDragOver}
                            onDragEnd={handleDragEnd}
                            onDragCancel={() => setActiveDropColumn(null)}
                        >
                            {statuses.length === 0 ? (
                                <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
                                    Add your first role to start building a pipeline.
                                </div>
                            ) : (
                                <div className="flex flex-wrap gap-4 pb-8">
                                    {columnConfigs.map((column) => (
                                        <div key={column.id} className="flex-1 min-w-[260px] basis-72">
                                            <BoardColumn
                                                status={column.id}
                                                title={column.label}
                                                jobs={grouped.get(column.id) ?? []}
                                                totalCount={totalsByColumn.get(column.id) ?? 0}
                                                onSelect={(card) => setSelectedJobId(card.id)}
                                                highlight={activeDropColumn === column.id}
                                            />
                                        </div>
                                    ))}
                                </div>
                            )}
                        </DndContext>
                    </div>
                </section>
            </main>

            <DemoBoardDrawer
                key={selectedJob?.id ?? "demo-demo-drawer"}
                job={selectedJob}
                detail={selectedDetail}
                open={Boolean(selectedJob)}
                availableStatuses={columnConfigs.flatMap((column) => column.statuses)}
                onClose={() => setSelectedJobId(null)}
                onStatusChange={(nextStatus) => selectedJob && handleStatusChange(selectedJob.id, nextStatus)}
                onMomentum={(update) => selectedJob && handleMomentumUpdate(selectedJob.id, update)}
                onUpdateDetail={handleDetailUpdate}
            />

            <footer className="border-t border-slate-200 py-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
                <p>Ready for the real thing? Create an account and import your pipeline in minutes.</p>
            </footer>
        </div>
    );
}


