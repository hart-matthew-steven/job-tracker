import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Clock, ExternalLink, Loader2, MapPin, Check } from "lucide-react";

import {
  addNote,
  deleteNote,
  getJobDetails,
  listJobActivity,
  patchJob,
  createInterview,
  deleteInterview,
} from "../../api";
import type { JobActivity, JobBoardCard, JobDetailsBundle } from "../../types/api";
import { useToast } from "../ui/toast";
import NotesCard from "../jobs/NotesCard";
import InterviewsCard, { type InterviewDraft } from "../jobs/InterviewsCard";
import TimelineCard from "../jobs/TimelineCard";
import DocumentsPanel from "../documents/DocumentsPanel";

type Props = {
  jobId: number | null;
  onClose: () => void;
  onCardUpdate: (patch: Partial<JobBoardCard> & { id: number }) => void;
  onRefreshBoard: () => void;
  open: boolean;
};

const ACTIVITY_PAGE_SIZE = 20;

export function BoardDrawer({ jobId, onClose, onCardUpdate, onRefreshBoard, open }: Props) {
  const [bundle, setBundle] = useState<JobDetailsBundle | null>(null);
  const [loading, setLoading] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [saving, setSaving] = useState(false);
  const [activityItems, setActivityItems] = useState<JobActivity[]>([]);
  const [activityCursor, setActivityCursor] = useState<number | null>(null);
  const [activityLoadingMore, setActivityLoadingMore] = useState(false);
  const [activityLoadingInitial, setActivityLoadingInitial] = useState(false);
  const [activityError, setActivityError] = useState("");
  const activityLoadRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const toast = useToast();

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const syncBundle = useCallback((data: JobDetailsBundle) => {
    setBundle(data);
  }, []);

  const loadActivityPage = useCallback(
    async ({ cursor = null, reset = false }: { cursor?: number | null; reset?: boolean } = {}) => {
      if (!jobId) return;
      if (activityLoadRef.current) return;

      if (cursor) {
        setActivityLoadingMore(true);
      } else {
        setActivityLoadingInitial(true);
        if (reset) {
          setActivityItems([]);
          setActivityCursor(null);
        }
      }

      activityLoadRef.current = true;

      setActivityError("");

      try {
        const page = await listJobActivity(jobId, {
          limit: ACTIVITY_PAGE_SIZE,
          cursor_id: cursor ?? undefined,
        });

        const items = Array.isArray(page.items) ? page.items : [];
        setActivityItems((prev) => {
          const base = cursor && !reset ? [...prev] : [];
          const seen = new Set(base.map((item) => item.id));
          for (const item of items) {
            if (!seen.has(item.id)) {
              base.push(item);
              seen.add(item.id);
            }
          }
          return base;
        });
        setActivityCursor(page.next_cursor ?? null);
      } catch (err) {
        const msg = (err as { message?: string } | null)?.message ?? "Unable to load activity";
        setActivityError(msg);
      } finally {
        if (cursor) {
          setActivityLoadingMore(false);
        } else {
          setActivityLoadingInitial(false);
        }
        activityLoadRef.current = false;
      }
    },
    [jobId]
  );

  useEffect(() => {
    if (!open || !jobId) return;
    let cancelled = false;
    setLoading(true);
    getJobDetails(jobId)
      .then((data) => {
        if (!cancelled) syncBundle(data);
      })
      .catch((err) => {
        if (!cancelled) {
          toast.error(err.message || "Unable to load job");
          onCloseRef.current?.();
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, open, syncBundle, toast]);

  useEffect(() => {
    if (!open) {
      document.body.classList.remove("drawer-open");
      return;
    }
    document.body.classList.add("drawer-open");
    return () => {
      document.body.classList.remove("drawer-open");
    };
  }, [open]);

  useEffect(() => {
    if (!open || !jobId) return;
    setActivityItems([]);
    setActivityCursor(null);
    setActivityError("");
    void loadActivityPage({ reset: true });
  }, [open, jobId, loadActivityPage]);

  const job = bundle?.job;
  const interviews = bundle?.interviews ?? [];

  const refreshJobDetails = useCallback(async () => {
    if (!jobId) return;
    try {
      const updated = await getJobDetails(jobId);
      syncBundle(updated);
    } catch (err) {
      toast.error((err as Error).message || "Unable to refresh job");
    }
  }, [jobId, syncBundle, toast]);

  const nextActionDefaults = useMemo(() => {
    if (!job?.next_action_at) return "";
    try {
      const dt = new Date(job.next_action_at);
      return dt.toISOString().slice(0, 16);
    } catch {
      return "";
    }
  }, [job?.next_action_at]);

  if (!open || !jobId) return null;

  async function handleStatusChange(status: string) {
    if (!job || status === job.status) return;
    const currentJobId = jobId;
    if (!currentJobId) return;
    const previousJob = job;

    setBundle((prev) => (prev ? { ...prev, job: { ...prev.job, status } } : prev));
    onCardUpdate({
      id: currentJobId,
      status,
      updated_at: job.updated_at,
    });

    try {
      setSaving(true);
      const updated = await patchJob(currentJobId, { status });
      setBundle((prev) =>
        prev
          ? {
            ...prev,
            job: {
              ...prev.job,
              ...updated,
            },
          }
          : prev
      );
      onCardUpdate({
        id: updated.id,
        status: updated.status ?? status,
        updated_at: updated.updated_at,
        last_action_at: updated.last_action_at,
        next_action_at: updated.next_action_at,
        next_action_title: updated.next_action_title,
      });
      toast.success("Status updated", "Board");
    } catch (err) {
      setBundle((prev) => (prev ? { ...prev, job: previousJob } : prev));
      onCardUpdate({
        id: previousJob.id,
        status: previousJob.status ?? status,
        updated_at: previousJob.updated_at,
      });
      toast.error((err as Error).message || "Unable to update status");
    } finally {
      setSaving(false);
    }
  }

  async function handleMomentum(action: "follow_up" | "apply" | "reminder") {
    if (!job || !jobId) return;
    const currentJobId = jobId;
    const now = new Date();
    const next = new Date(now);
    next.setDate(now.getDate() + (action === "reminder" ? 1 : 3));
    const title =
      action === "apply" ? "Send application" : action === "follow_up" ? "Follow up" : "Prep reminder";
    try {
      setSaving(true);
      const updated = await patchJob(currentJobId, {
        last_action_at: now.toISOString(),
        next_action_at: next.toISOString(),
        next_action_title: title,
      });
      setBundle((prev) =>
        prev
          ? {
            ...prev,
            job: {
              ...prev.job,
              last_action_at: updated.last_action_at ?? now.toISOString(),
              next_action_at: updated.next_action_at ?? next.toISOString(),
              next_action_title: updated.next_action_title ?? title,
            },
          }
          : prev
      );
      onCardUpdate({
        id: currentJobId,
        last_action_at: updated.last_action_at ?? now.toISOString(),
        next_action_at: updated.next_action_at ?? next.toISOString(),
        next_action_title: updated.next_action_title ?? title,
        needs_follow_up: false,
      });
      await refreshJobDetails();
      onRefreshBoard();
      toast.success("Momentum logged", "Board");
    } catch (err) {
      toast.error((err as Error).message || "Unable to update momentum");
    } finally {
      setSaving(false);
    }
  }

  async function handleNextActionSave(formData: FormData) {
    if (!job || !jobId) return;
    const currentJobId = jobId;
    const title = String(formData.get("next_title") || "");
    const when = String(formData.get("next_when") || "");
    if (!when) {
      toast.error("Pick a target date/time", "Next action");
      return;
    }
    try {
      setSaving(true);
      const updated = await patchJob(currentJobId, {
        next_action_at: new Date(when).toISOString(),
        next_action_title: title || null,
      });
      setBundle((prev) =>
        prev
          ? {
            ...prev,
            job: {
              ...prev.job,
              next_action_at: updated.next_action_at ?? new Date(when).toISOString(),
              next_action_title: updated.next_action_title ?? title,
            },
          }
          : prev
      );
      onCardUpdate({
        id: currentJobId,
        next_action_at: updated.next_action_at ?? new Date(when).toISOString(),
        next_action_title: updated.next_action_title ?? title,
        needs_follow_up: false,
      });
      toast.success("Next action scheduled", "Board");
      await refreshJobDetails();
      await loadActivityPage({ reset: true });
    } catch (err) {
      toast.error((err as Error).message || "Unable to schedule next action");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddNote() {
    if (!noteText.trim() || !job) return;
    try {
      await addNote(job.id, { body: noteText.trim() });
      setNoteText("");
      await refreshJobDetails();
      await loadActivityPage({ reset: true });
      toast.success("Note added", "Board");
      onRefreshBoard();
    } catch (err) {
      toast.error((err as Error).message || "Unable to add note");
    }
  }

  async function handleDeleteNote(noteId: number) {
    if (!job) return;
    try {
      await deleteNote(job.id, noteId);
      await refreshJobDetails();
      await loadActivityPage({ reset: true });
      toast.success("Note removed", "Board");
    } catch (err) {
      toast.error((err as Error).message || "Unable to delete note");
    }
  }

  async function handleCreateInterview(draft: InterviewDraft) {
    if (!job) return;
    try {
      await createInterview(job.id, {
        scheduled_at: draft.scheduled_at,
        stage: draft.stage || null,
        kind: draft.kind || null,
        location: draft.location || null,
        interviewer: draft.interviewer || null,
        status: draft.status || "scheduled",
        notes: draft.notes || null,
      });
      toast.success("Interview added", "Board drawer");
      await refreshJobDetails();
      await loadActivityPage({ reset: true });
    } catch (err) {
      toast.error((err as Error).message || "Unable to add interview");
    }
  }

  async function handleDeleteInterview(id: number) {
    if (!job) return;
    try {
      await deleteInterview(job.id, id);
      toast.success("Interview deleted", "Board drawer");
      await refreshJobDetails();
      await loadActivityPage({ reset: true });
    } catch (err) {
      toast.error((err as Error).message || "Unable to delete interview");
    }
  }

  function handleDocumentActivity() {
    void refreshJobDetails();
    void loadActivityPage({ reset: true });
    onRefreshBoard();
  }

  async function handleLoadMoreActivity() {
    if (!activityCursor || activityLoadingMore) return;
    await loadActivityPage({ cursor: activityCursor });
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="hidden flex-1 bg-black/50 lg:block" onClick={onClose} aria-hidden="true" />
      <aside className="relative ml-auto flex h-full w-full max-w-xl flex-col border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Details</p>
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">{job?.company_name}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">{job?.job_title}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-slate-600 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          >
            Close
          </button>
        </div>

        {loading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        )}

        {!loading && job && (
          <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
            <div className="space-y-2 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={job.status ?? "applied"}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="rounded-full border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  disabled={saving}
                >
                  <option value="applied">Applied</option>
                  <option value="recruiter_screen">Recruiter screen</option>
                  <option value="interviewing">Interviewing</option>
                  <option value="onsite">Onsite</option>
                  <option value="offer">Offer</option>
                  <option value="accepted">Accepted</option>
                  <option value="rejected">Rejected</option>
                  <option value="withdrawn">Withdrawn</option>
                  <option value="archived">Archived</option>
                </select>
                {job.job_url && (
                  <a
                    href={job.job_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-medium text-sky-600 hover:underline"
                  >
                    View posting <ExternalLink size={14} aria-hidden="true" />
                  </a>
                )}
              </div>
              {job.location && (
                <p className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400">
                  <MapPin size={14} aria-hidden="true" /> {job.location}
                </p>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 p-4 shadow-sm dark:border-slate-800">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Momentum mode</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <button
                  type="button"
                  onClick={() => handleMomentum("follow_up")}
                  className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200"
                >
                  Log follow-up
                </button>
                <button
                  type="button"
                  onClick={() => handleMomentum("apply")}
                  className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200"
                >
                  Mark applied
                </button>
                <button
                  type="button"
                  onClick={() => handleMomentum("reminder")}
                  className="rounded-2xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 dark:border-slate-700 dark:text-slate-200"
                >
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
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  handleNextActionSave(data as FormData);
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
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
                  disabled={saving}
                >
                  <Check size={14} aria-hidden="true" /> Save next action
                </button>
              </form>
            </div>

            <NotesCard
              notes={bundle?.notes ?? []}
              noteText={noteText}
              setNoteText={setNoteText}
              onAddNote={handleAddNote}
              onDeleteNote={handleDeleteNote}
            />

            <InterviewsCard
              items={interviews}
              loading={false}
              error=""
              onCreate={handleCreateInterview}
              onDelete={handleDeleteInterview}
            />

            <TimelineCard
              items={activityItems}
              loading={activityLoadingInitial}
              loadingMore={activityLoadingMore}
              hasMore={Boolean(activityCursor)}
              error={activityError}
              onLoadMore={handleLoadMoreActivity}
            />

            <DocumentsPanel jobId={job.id} onActivityChange={() => handleDocumentActivity()} />
          </div>
        )}
      </aside>
    </div>
  );
}
