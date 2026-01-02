import { useMemo, useState } from "react";
import type { JobInterview } from "../../types/api";
import Modal from "../ui/Modal";
import CollapseToggle from "../ui/CollapseToggle";

function fmtDateTime(dt: string | null | undefined) {
  if (!dt) return "—";
  const d = new Date(dt);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "numeric",
    minute: "2-digit",
  });
}

function toLocalInputValue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(v: string): string {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return new Date().toISOString();
  return d.toISOString();
}

type Draft = {
  scheduled_at: string;
  stage: string;
  kind: string;
  location: string;
  interviewer: string;
  status: string;
  notes: string;
};

type Props = {
  items: JobInterview[];
  loading?: boolean;
  error?: string;
  onCreate: (draft: Draft) => Promise<void> | void;
  onDelete: (id: number) => Promise<void> | void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
};

export default function InterviewsCard({
  items,
  loading = false,
  error = "",
  onCreate,
  onDelete,
  collapsed = false,
  onToggleCollapse,
}: Props) {
  const labelClass = "block text-sm font-medium text-slate-700 dark:text-slate-200";
  const fieldClass =
    "mt-1 w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-600/30 " +
    "border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 " +
    "dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400";

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => ({
    scheduled_at: new Date().toISOString(),
    stage: "",
    kind: "",
    location: "",
    interviewer: "",
    status: "scheduled",
    notes: "",
  }));

  const sorted = useMemo(() => {
    const list = Array.isArray(items) ? [...items] : [];
    list.sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());
    return list;
  }, [items]);

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xl font-semibold">Interviews</div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900"
          >
            + Add interview
          </button>
          {onToggleCollapse && <CollapseToggle collapsed={collapsed} onToggle={onToggleCollapse} label="interviews section" />}
        </div>
      </div>

      {!collapsed && (
        <>
          {error && (
            <div className="mt-3 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}

          {loading && <div className="mt-3 text-sm text-slate-400">Loading…</div>}

          {!loading && !error && (!sorted || sorted.length === 0) && (
            <div className="mt-3 text-sm text-slate-400">No interviews yet.</div>
          )}

          <div className="mt-4 space-y-3">
            {sorted?.map((iv) => (
              <div key={iv.id} className="rounded-lg border border-slate-800 bg-slate-950/30 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-100">
                      {fmtDateTime(iv.scheduled_at)}{" "}
                      <span className="text-slate-400 font-medium">
                        ({(iv.status ?? "scheduled").toLowerCase()})
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-slate-400">
                      {[iv.stage, iv.kind, iv.interviewer].filter(Boolean).join(" • ") || "—"}
                    </div>
                    {iv.location && <div className="mt-1 text-xs text-slate-500 break-words">{iv.location}</div>}
                    {iv.notes && <div className="mt-2 text-sm text-slate-200 whitespace-pre-wrap break-words">{iv.notes}</div>}
                  </div>

                  <button
                    type="button"
                    onClick={() => onDelete(iv.id)}
                    className="shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition border border-red-800/70 bg-red-950/20 text-red-200 hover:bg-red-950/30"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add interview"
        maxWidthClassName="max-w-2xl"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void (async () => {
              await onCreate(draft);
              setOpen(false);
              setDraft({
                scheduled_at: new Date().toISOString(),
                stage: "",
                kind: "",
                location: "",
                interviewer: "",
                status: "scheduled",
                notes: "",
              });
            })();
          }}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Date & time</label>
              <input
                type="datetime-local"
                value={toLocalInputValue(draft.scheduled_at)}
                onChange={(e) => setDraft((p) => ({ ...p, scheduled_at: fromLocalInputValue(e.target.value) }))}
                className={fieldClass}
                required
              />
            </div>
            <div>
              <label className={labelClass}>Status</label>
              <select
                value={draft.status}
                onChange={(e) => setDraft((p) => ({ ...p, status: e.target.value }))}
                className={fieldClass}
              >
                <option value="scheduled">Scheduled</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Stage</label>
              <input
                value={draft.stage}
                onChange={(e) => setDraft((p) => ({ ...p, stage: e.target.value }))}
                className={fieldClass}
                placeholder="e.g. recruiter screen"
              />
            </div>
            <div>
              <label className={labelClass}>Type</label>
              <input
                value={draft.kind}
                onChange={(e) => setDraft((p) => ({ ...p, kind: e.target.value }))}
                className={fieldClass}
                placeholder="e.g. phone / video / onsite"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Interviewer</label>
              <input
                value={draft.interviewer}
                onChange={(e) => setDraft((p) => ({ ...p, interviewer: e.target.value }))}
                className={fieldClass}
                placeholder="Optional"
              />
            </div>
            <div>
              <label className={labelClass}>Location / link</label>
              <input
                value={draft.location}
                onChange={(e) => setDraft((p) => ({ ...p, location: e.target.value }))}
                className={fieldClass}
                placeholder="Address or URL"
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>Notes</label>
            <textarea
              value={draft.notes}
              onChange={(e) => setDraft((p) => ({ ...p, notes: e.target.value }))}
              className={`${fieldClass} min-h-24`}
              placeholder="Anything you want to remember"
            />
          </div>

          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg px-4 py-2 text-sm font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-200 dark:hover:bg-slate-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-lg px-4 py-2 text-sm font-semibold transition border border-slate-300 bg-slate-900 text-white hover:bg-slate-800 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900"
            >
              Save
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}


