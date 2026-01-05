import { useCallback, useEffect, useMemo, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import {
    DndContext,
    DragCancelEvent,
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
import type { JobBoardCard, JobsBoardResponse, PatchJobIn } from "../types/api";
import { getBoardSnapshot, patchJob, createJob } from "../api";
import { moveBoardCard } from "../lib/boardState";
import { BoardColumn } from "../components/board/BoardColumn";
import { BoardDrawer } from "../components/board/BoardDrawer";
import { BoardHeader } from "../components/board/BoardHeader";
import { BoardFilters } from "../components/board/BoardFilters";
import { useToast } from "../components/ui/toast";
import Modal from "../components/ui/Modal";
import JobCard from "../components/jobs/JobCard";
import type { ShellContext } from "../components/layout/AppShell";

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

type JobFormState = {
  company_name: string;
  job_title: string;
  location: string;
  job_url: string;
};

const INITIAL_FORM: JobFormState = {
  company_name: "",
  job_title: "",
  location: "",
  job_url: "",
};

export default function BoardPage() {
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [snapshot, setSnapshot] = useState<JobsBoardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(() => searchParams.get("create") === "1");
  const [form, setForm] = useState<JobFormState>(INITIAL_FORM);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const shell = useOutletContext<ShellContext | null>();
  const [followUpsOnly, setFollowUpsOnly] = useState(false);
  const [activeDropColumn, setActiveDropColumn] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const selectedJobId = useMemo(() => {
    if (activeJobId) return activeJobId;
    const paramId = Number(searchParams.get("jobId"));
    return Number.isFinite(paramId) ? paramId : null;
  }, [activeJobId, searchParams]);

  useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  const closeCreateModal = useCallback(() => {
    setCreateOpen(false);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("create");
      return next;
    });
  }, [setSearchParams]);

  const loadBoard = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getBoardSnapshot();
      setSnapshot(data);
    } catch (err) {
      toast.error((err as Error).message || "Unable to load board");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  const columnConfigs = useMemo(() => {
    const configs = BASE_COLUMN_GROUPS.map((group) => ({ ...group }));
    const known = new Set(configs.flatMap((group) => group.statuses));
    const statuses = snapshot?.statuses ?? [];
    statuses.forEach((status) => {
      if (!known.has(status)) {
        configs.push({
          id: status,
          label: formatStatusLabel(status),
          statuses: [status],
          defaultStatus: status,
        });
        known.add(status);
      }
    });
    return configs;
  }, [snapshot?.statuses]);

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

  const totalsByColumn = useMemo(() => {
    const counts = new Map<string, number>();
    columnConfigs.forEach((column) => counts.set(column.id, 0));
    (snapshot?.jobs || []).forEach((card) => {
      const key = statusToColumnId.get(card.status) ?? card.status;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return counts;
  }, [snapshot, columnConfigs, statusToColumnId]);

  const filteredGrouped = useMemo(() => {
    const map = new Map<string, JobBoardCard[]>();
    columnConfigs.forEach((column) => map.set(column.id, []));
    (snapshot?.jobs || []).forEach((card) => {
      const columnId = statusToColumnId.get(card.status) ?? card.status;
      if (followUpsOnly && !card.needs_follow_up) return;
      if (!map.has(columnId)) {
        map.set(columnId, []);
      }
      map.get(columnId)!.push(card);
    });
    return map;
  }, [snapshot, columnConfigs, statusToColumnId, followUpsOnly]);

  const hasVisibleCards = useMemo(() => Array.from(filteredGrouped.values()).some((list) => list.length > 0), [filteredGrouped]);

  const handleCardSelect = useCallback(
    (card: JobBoardCard) => {
      setActiveJobId(card.id);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("jobId", String(card.id));
        return next;
      });
    },
    [setSearchParams]
  );

  function handleDrawerClose() {
    setActiveJobId(null);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("jobId");
      return next;
    });
  }

  function updateCard(patch: Partial<JobBoardCard> & { id: number }) {
    setSnapshot((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        jobs: prev.jobs.map((card) => (card.id === patch.id ? { ...card, ...patch } : card)),
      };
    });
  }

  const resolveColumnFromOver = useCallback((over: DragOverEvent["over"]) => {
    if (!over) return null;
    const data = (over.data?.current as { columnId?: string } | undefined) ?? undefined;
    if (data?.columnId) return data.columnId;
    if (typeof over.id === "string" && over.id.startsWith("column-")) {
      return over.id.replace("column-", "");
    }
    return null;
  }, []);

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const columnId = event.active.data.current?.columnId as string | undefined;
      if (columnId) {
        setActiveDropColumn(columnId);
      }
    },
    []
  );

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const columnId = resolveColumnFromOver(event.over);
      if (columnId) {
        setActiveDropColumn(columnId);
      }
    },
    [resolveColumnFromOver]
  );

  const handleDragCancel = useCallback(() => {
    setActiveDropColumn(null);
  }, []);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setActiveDropColumn(null);
    if (!active || !over) return;
    const jobId = Number(active.id);
    const sourceColumnId = active.data.current?.columnId as string | undefined;
    const targetColumnId = resolveColumnFromOver(over);
    if (!jobId || !sourceColumnId || !targetColumnId) return;
    if (sourceColumnId === targetColumnId) return;

    const nextStatus = columnDefaultStatus.get(targetColumnId) ?? targetColumnId;

    const prev = snapshot;
    setSnapshot((current) => moveBoardCard(current, jobId, nextStatus));

    try {
      const payload: PatchJobIn = { status: nextStatus };
      await patchJob(jobId, payload);
      loadBoard();
    } catch (err) {
      toast.error((err as Error).message || "Unable to move card");
      setSnapshot(prev);
    }
  }

  async function handleCreateJob(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await createJob({ ...form });
      setForm(INITIAL_FORM);
      closeCreateModal();
      toast.success("Job created", "Board");
      loadBoard();
    } catch (err) {
      toast.error((err as Error).message || "Unable to create job");
    }
  }

  async function handleRefreshBoard() {
    setIsRefreshing(true);
    await loadBoard();
    shell?.refreshPulse();
    setIsRefreshing(false);
  }

  if (loading && !snapshot) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-sm text-slate-500">Loading board…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <BoardHeader isRefreshing={isRefreshing} onRefresh={handleRefreshBoard} />
      <BoardFilters followUpsOnly={followUpsOnly} onToggleFollowUps={() => setFollowUpsOnly((v) => !v)} />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragCancel={handleDragCancel}
        onDragEnd={handleDragEnd}
      >
        {columnConfigs.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
            Add your first role to start building a pipeline.
          </div>
        ) : hasVisibleCards ? (
          <div className="flex flex-wrap gap-4 pb-8">
            {columnConfigs.map((column) => (
              <div key={column.id} className="flex-1 min-w-[260px] basis-72">
                <BoardColumn
                  status={column.id}
                  title={column.label}
                  jobs={filteredGrouped.get(column.id) || []}
                  totalCount={totalsByColumn.get(column.id) ?? 0}
                  onSelect={handleCardSelect}
                  highlight={activeDropColumn === column.id}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-300">
            No roles match your filters. Try clearing search or toggles.
          </div>
        )}
      </DndContext>

      <BoardDrawer
        jobId={selectedJobId}
        onClose={handleDrawerClose}
        onCardUpdate={updateCard}
        onRefreshBoard={handleRefreshBoard}
        open={Boolean(selectedJobId)}
      />

      <Modal open={createOpen} onClose={closeCreateModal} title="Create role">
        <JobCard form={form} setForm={setForm} onCreateJob={handleCreateJob} title={null} />
      </Modal>
    </div>
  );
}

