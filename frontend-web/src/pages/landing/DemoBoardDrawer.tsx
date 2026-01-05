import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Check, Clock, ExternalLink, Loader2, MapPin, Paperclip, Sparkles } from "lucide-react";
import type { JobBoardCard } from "../../types/api";
import type { DemoActivity, DemoDocument, DemoInterview, DemoJobDetail, DemoNote } from "./demoBoardData";
import type { JobActivity, JobInterview } from "../../types/api";
import NotesCard from "../../components/jobs/NotesCard";
import InterviewsCard from "../../components/jobs/InterviewsCard";
import TimelineCard from "../../components/jobs/TimelineCard";

type MomentumUpdate = {
  last_action_at?: string | null;
  next_action_at?: string | null;
  next_action_title?: string | null;
};

type Props = {
  job: JobBoardCard | null;
  detail?: DemoJobDetail;
  open: boolean;
  onClose: () => void;
  onStatusChange: (nextStatus: string) => void;
  onMomentum: (update: MomentumUpdate) => void;
  onUpdateDetail: (detail: DemoJobDetail) => void;
  availableStatuses: string[];
};

export function DemoBoardDrawer({
  job,
  detail,
  open,
  onClose,
  onStatusChange,
  onMomentum,
  onUpdateDetail,
  availableStatuses,
}: Props) {
  const [noteText, setNoteText] = useState("");
  const idRef = useRef(1000);

  const nextId = useCallback(() => {
    idRef.current += 1;
    return idRef.current;
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const nextActionDefaults = useMemo(() => {
    if (!job?.next_action_at) return "";
    try {
      return new Date(job.next_action_at).toISOString().slice(0, 16);
    } catch {
      return "";
    }
  }, [job]);

  const appendActivity = useCallback(
    (base: DemoJobDetail, entry: Partial<DemoActivity> & { message: string }): DemoJobDetail => {
      const activity: DemoActivity = {
        id: nextId(),
        type: entry.type ?? "demo_event",
        message: entry.message,
        created_at: new Date().toISOString(),
      };
      return { ...base, activity: [activity, ...(base.activity || [])] };
    },
    [nextId]
  );

  if (!open || !job) return null;
  if (!detail) {
    return (
      <div className="fixed inset-0 z-50 flex">
        <div className="hidden flex-1 bg-black/50 lg:block" onClick={onClose} aria-hidden="true" />
        <aside className="ml-auto flex h-full w-full max-w-xl flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        </aside>
      </div>
    );
  }

  const handleStatusChange = (status: string) => {
    onStatusChange(status);
    onUpdateDetail(appendActivity(detail, { type: "status_changed", message: `Status moved to ${status.replace(/_/g, " ")}.` }));
  };

  const handleMomentumAction = (kind: "follow_up" | "apply" | "reminder") => {
    const now = new Date();
    const next = new Date(now);
    next.setDate(now.getDate() + (kind === "reminder" ? 1 : 3));
    const label = kind === "apply" ? "Send application" : kind === "follow_up" ? "Follow up" : "Reminder";
    onMomentum({ last_action_at: now.toISOString(), next_action_at: next.toISOString(), next_action_title: label });
    onUpdateDetail(appendActivity(detail, { type: "momentum", message: `Logged "${label}" for ${next.toLocaleDateString()}.` }));
  };

  const handleScheduleNext = (formData: FormData) => {
    const title = String(formData.get("next_title") || "");
    const when = String(formData.get("next_when") || "");
    if (!when) return;
    const whenIso = new Date(when).toISOString();
    onMomentum({ next_action_at: whenIso, next_action_title: title });
    onUpdateDetail(appendActivity(detail, { type: "next_action", message: `Scheduled "${title || "Next action"}" for ${new Date(whenIso).toLocaleString()}.` }));
  };

  const handleAddNote = () => {
    if (!noteText.trim()) return;
    const note: DemoNote = { id: nextId(), body: noteText.trim(), created_at: new Date().toISOString() };
    const withNote = { ...detail, notes: [note, ...(detail.notes || [])] };
    onUpdateDetail(appendActivity(withNote, { type: "note_added", message: "Added a note in the demo board." }));
    setNoteText("");
  };

  const handleDeleteNote = (noteId: number) => {
    const withDeletion = { ...detail, notes: (detail.notes || []).filter((note) => note.id !== noteId) };
    onUpdateDetail(appendActivity(withDeletion, { type: "note_deleted", message: "Removed a note on the demo board." }));
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="hidden flex-1 bg-black/50 lg:block" onClick={onClose} aria-hidden="true" />
      <aside className="relative ml-auto flex h-full w-full max-w-xl flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Demo details</p>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{job.company_name}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">{job.job_title}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          >
            Close
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-600">
            <Sparkles size={14} aria-hidden="true" /> Demo data only — no account required
          </div>

          <div className="space-y-2 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={job.status ?? "applied"}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="rounded-full border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                {availableStatuses.map((status) => (
                  <option key={status} value={status}>
                    {status.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              {detail.job_url && (
                <a href={detail.job_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-sky-600 hover:underline">
                  View posting <ExternalLink size={14} aria-hidden="true" />
                </a>
              )}
            </div>
            {job.location && (
              <p className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400">
                <MapPin size={14} aria-hidden="true" /> {job.location}
              </p>
            )}
            <p className="text-sm text-slate-500 dark:text-slate-400">{detail.summary}</p>
          </div>

          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm dark:border-slate-800">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Momentum mode</p>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <button type="button" onClick={() => handleMomentumAction("follow_up")} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200">
                Log follow-up
              </button>
              <button type="button" onClick={() => handleMomentumAction("apply")} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200">
                Mark applied
              </button>
              <button type="button" onClick={() => handleMomentumAction("reminder")} className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200">
                Nudge tomorrow
              </button>
            </div>
            <div className="mt-4 space-y-2 text-sm text-slate-500 dark:text-slate-400">
              {job.last_action_at && (
                <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  <CalendarDays size={14} aria-hidden="true" />
                  Last action {new Date(job.last_action_at).toLocaleDateString()}
                </div>
              )}
              {job.next_action_at && (
                <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  <Clock size={14} aria-hidden="true" />
                  Next: {job.next_action_title || "Reminder"} on {new Date(job.next_action_at).toLocaleDateString()}
                </div>
              )}
            </div>
            <form
              className="mt-4 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                handleScheduleNext(new FormData(event.currentTarget));
              }}
            >
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Next action title</label>
                <input
                  name="next_title"
                  defaultValue={job.next_action_title ?? ""}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  placeholder="e.g. Send thank-you note"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">When</label>
                <input
                  name="next_when"
                  defaultValue={nextActionDefaults}
                  type="datetime-local"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
              </div>
              <button type="submit" className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900">
                <Check size={14} aria-hidden="true" /> Save next action
              </button>
            </form>
          </div>

          <NotesCard
            notes={detail.notes}
            noteText={noteText}
            setNoteText={setNoteText}
            onAddNote={handleAddNote}
            onDeleteNote={handleDeleteNote}
            isDemo
          />

          <InterviewsCard
            items={detail.interviews as unknown as JobInterview[]}
            loading={false}
            error=""
            onCreate={() => undefined}
            onDelete={() => undefined}
            demoMode
          />

          <section className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Documents</p>
            {detail.documents.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">No uploads yet.</p>}
            {detail.documents.map((doc: DemoDocument) => (
              <div key={doc.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Paperclip size={14} aria-hidden="true" className="text-slate-400" />
                  <div>
                    <p className="font-semibold text-slate-900 dark:text-slate-100">{doc.name}</p>
                    <p className="text-xs text-slate-500">{new Date(doc.uploaded_at).toLocaleString()}</p>
                  </div>
                </div>
                <span
                  className={[
                    "rounded-full px-3 py-1 text-xs font-semibold",
                    doc.status === "CLEAN"
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-200"
                      : doc.status === "PENDING"
                        ? "bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-200"
                        : "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-200",
                  ].join(" ")}
                >
                  {doc.status}
                </span>
              </div>
            ))}
          </section>

          <TimelineCard
            items={detail.activity as unknown as JobActivity[]}
            loading={false}
            loadingMore={false}
            hasMore={false}
            error=""
            onLoadMore={() => undefined}
            demoMode
          />
        </div>
      </aside>
    </div>
  );
}


