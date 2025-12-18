// src/pages/JobsPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import DocumentsPanel from "../components/documents/DocumentsPanel";
import JobsList from "../components/jobs/JobsList";
import NotesCard from "../components/jobs/NotesCard";
import JobDetailsCard from "../components/jobs/JobDetailsCard";
import JobCard from "../components/jobs/JobCard";

import { useSettings } from "../hooks/useSettings";

import {
  listJobs,
  getJob,
  createJob as apiCreateJob,
  patchJob,
  listNotes,
  addNote as apiAddNote,
  deleteNote as apiDeleteNote,
} from "../api";
import type { Job, Note, CreateJobIn } from "../types/api";

function jobSortKey(job: Job | null | undefined) {
  return job?.last_activity_at ?? job?.applied_date ?? job?.created_at ?? null;
}

function safeTime(value: string | null | undefined) {
  const t = new Date(value ?? 0).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function sortJobsDesc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) => safeTime(jobSortKey(b)) - safeTime(jobSortKey(a)));
  return copy;
}

function sortNotesDesc(list: Note[]) {
  const copy = [...list];
  copy.sort((a, b) => safeTime(b?.created_at) - safeTime(a?.created_at));
  return copy;
}

function sortJobsCompanyAsc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) =>
    String(a?.company_name ?? "").localeCompare(String(b?.company_name ?? ""), undefined, {
      sensitivity: "base",
    })
  );
  return copy;
}

function sortJobsStatusAsc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) =>
    String(a?.status ?? "").localeCompare(String(b?.status ?? ""), undefined, {
      sensitivity: "base",
    })
  );
  return copy;
}

function matchesJob(job: Job, q: string) {
  const query = String(q ?? "").trim().toLowerCase();
  if (!query) return true;

  const hay = [job?.company_name, job?.job_title, job?.location, job?.status]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return hay.includes(query);
}

function hasOpenModal() {
  return Boolean(document.querySelector('dialog[open], [role="dialog"], [aria-modal="true"], [data-modal="true"]'));
}

function isTypingInInput() {
  const el = document.activeElement;
  if (!el) return false;
  if ((el as HTMLElement).isContentEditable) return true;

  const tag = String((el as Element).tagName ?? "").toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}

export default function JobsPage() {
  const { settings } = useSettings();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);

  type JobFormState = {
    company_name: string;
    job_title: string;
    location: string;
    job_url: string;
  };

  const [form, setForm] = useState<JobFormState>({
    company_name: "",
    job_title: "",
    location: "",
    job_url: "",
  });

  const [noteText, setNoteText] = useState("");

  // Page state
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState("updated_desc");
  const [visibleCount, setVisibleCount] = useState(50);

  const selectedJobId = useMemo(() => selectedJob?.id ?? null, [selectedJob]);

  // Prevent out-of-order responses when clicking jobs quickly
  const selectSeqRef = useRef(0);
  const refreshSeqRef = useRef(0);
  const refreshJobsRef = useRef<(opts?: { source?: string }) => void>(() => {});

  useEffect(() => {
    refreshJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  refreshJobsRef.current = refreshJobs;

  useEffect(() => {
    const seconds = Number(settings?.autoRefreshSeconds ?? 0);
    if (!seconds) return;

    const intervalMs = Math.max(1, seconds) * 1000;
    const id = window.setInterval(() => {
      if (document.hidden) return;
      if (hasOpenModal()) return;
      if (isTypingInInput()) return;
      if (loadingJobs || loadingDetails) return;
      refreshJobsRef.current?.({ source: "auto" });
    }, intervalMs);

    function onVisibilityChange() {
      if (!document.hidden) {
        if (hasOpenModal()) return;
        if (isTypingInInput()) return;
        refreshJobsRef.current?.({ source: "visible" });
      }
    }

    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [settings?.autoRefreshSeconds, loadingJobs, loadingDetails]);

  async function refreshJobs({ source }: { source?: string } = {}) {
    setError("");
    setLoadingJobs(true);

    const prevScrollY = window.scrollY;
    const mySeq = ++refreshSeqRef.current;

    try {
      const data = await listJobs();
      const list = Array.isArray(data) ? (data as Job[]) : [];
      if (refreshSeqRef.current !== mySeq) return;
      setJobs(sortJobsDesc(list));
      setLastUpdatedAt(new Date());

      if (selectedJobId && !list.some((j) => j.id === selectedJobId)) {
        setSelectedJob(null);
        setNotes([]);
      }
    } catch (e) {
      if (refreshSeqRef.current !== mySeq) return;
      setError((e as { message?: string } | null)?.message ?? "Failed to load jobs");
      setJobs([]);
      setSelectedJob(null);
      setNotes([]);
    } finally {
      if (refreshSeqRef.current === mySeq) {
        setLoadingJobs(false);
        if (source !== "manual") {
          requestAnimationFrame(() => {
            window.scrollTo({ top: prevScrollY, left: 0, behavior: "auto" });
          });
        }
      }
    }
  }

  function upsertJob(updatedJob: Job) {
    setJobs((prev) => {
      const exists = prev.some((j) => j.id === updatedJob.id);
      const next = exists ? prev.map((j) => (j.id === updatedJob.id ? { ...j, ...updatedJob } : j)) : [...prev, updatedJob];
      return sortJobsDesc(next);
    });
  }

  const filteredSortedJobs = useMemo(() => {
    const filtered = jobs.filter((j) => matchesJob(j, search));

    if (sortMode === "company_asc") return sortJobsCompanyAsc(filtered);
    if (sortMode === "status_asc") return sortJobsStatusAsc(filtered);
    return sortJobsDesc(filtered);
  }, [jobs, search, sortMode]);

  const visibleJobs = useMemo(() => filteredSortedJobs.slice(0, visibleCount), [filteredSortedJobs, visibleCount]);

  const hasMore = visibleJobs.length < filteredSortedJobs.length;

  async function selectJob(job: Job) {
    if (!job?.id) return;

    setError("");
    setLoadingDetails(true);

    const mySeq = ++selectSeqRef.current;

    try {
      const freshJob = await getJob(job.id);
      if (selectSeqRef.current !== mySeq) return;

      setSelectedJob(freshJob);
      upsertJob(freshJob);

      const freshNotes = await listNotes(job.id);
      if (selectSeqRef.current !== mySeq) return;

      setNotes(sortNotesDesc(Array.isArray(freshNotes) ? (freshNotes as Note[]) : []));
    } catch (e) {
      if (selectSeqRef.current !== mySeq) return;
      setError((e as { message?: string } | null)?.message ?? "Failed to load job details");
    } finally {
      if (selectSeqRef.current === mySeq) setLoadingDetails(false);
    }
  }

  async function handleCreateJob(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    const payload: CreateJobIn = {
      company_name: form.company_name?.trim(),
      job_title: form.job_title?.trim(),
      location: form.location?.trim() || null,
      job_url: form.job_url?.trim() || null,
    };

    if (!payload.company_name || !payload.job_title) {
      setError("Company name and job title are required.");
      return;
    }

    try {
      const created = await apiCreateJob(payload);

      setForm({ company_name: "", job_title: "", location: "", job_url: "" });

      upsertJob(created);

      await selectJob(created);
    } catch (e2) {
      setError((e2 as { message?: string } | null)?.message ?? "Failed to create job");
    }
  }

  async function handleAddNote() {
    if (!selectedJob) return;
    setError("");

    const body = noteText.trim();
    if (!body) return;

    try {
      const created = await apiAddNote(selectedJob.id, { body });

      setNoteText("");
      setNotes((prev) => sortNotesDesc([created, ...prev]));
      bumpSelectedJobActivity(created.created_at ?? new Date().toISOString());
    } catch (e) {
      setError((e as { message?: string } | null)?.message ?? "Failed to add note");
    }
  }

  async function handleDeleteNote(noteId: number) {
    if (!selectedJob) return;
    setError("");

    try {
      await apiDeleteNote(selectedJob.id, noteId);

      const freshNotes = await listNotes(selectedJob.id);
      setNotes(sortNotesDesc(Array.isArray(freshNotes) ? (freshNotes as Note[]) : []));

      const freshJob = await getJob(selectedJob.id);
      setSelectedJob(freshJob);
      upsertJob(freshJob);
    } catch (e) {
      setError((e as { message?: string } | null)?.message ?? "Failed to delete note");
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!selectedJob) return;
    setError("");

    try {
      const updated = await patchJob(selectedJob.id, { status: newStatus });
      setSelectedJob(updated);
      upsertJob(updated);
    } catch (e) {
      setError((e as { message?: string } | null)?.message ?? "Failed to update status");
    }
  }

  function bumpSelectedJobActivity(iso: string) {
    if (!selectedJob) return;

    setSelectedJob((prev) => (prev ? { ...prev, last_activity_at: iso } : prev));

    setJobs((prev) => {
      const next = prev.map((j) => (j.id === selectedJob.id ? { ...j, last_activity_at: iso } : j));
      return sortJobsDesc(next);
    });
  }

  return (
    <div className="p-8">
      {error && (
        <div className="mb-6 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
          <div className="mt-2 text-xs text-slate-300">If this happened right after login, your session may have expired — try logging in again.</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* LEFT */}
        <div>
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h1 className="text-3xl font-bold">Jobs</h1>
              <div className="mt-1 text-xs text-slate-500">
                {lastUpdatedAt ? (
                  <>
                    Last updated <span className="text-slate-300 font-medium">{lastUpdatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
                  </>
                ) : (
                  " "
                )}
              </div>
            </div>
            {loadingJobs && <div className="text-xs text-slate-400">Refreshing…</div>}
          </div>

          <div className="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Search</label>
              <input value={search} onChange={(e) => { setSearch(e.target.value); setVisibleCount(50); }} className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-600/30" placeholder="Company, title, location, status…" />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Sort</label>
              <select value={sortMode} onChange={(e) => setSortMode(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-600/30">
                <option value="updated_desc">Updated (desc)</option>
                <option value="company_asc">Company (A→Z)</option>
                <option value="status_asc">Status</option>
              </select>
            </div>
          </div>

          <JobCard form={form} setForm={setForm} onCreateJob={handleCreateJob} />

          {loadingJobs ? (
            <div className="mt-4 text-sm text-slate-400">Loading jobs…</div>
          ) : (
            <>
              <JobsList jobs={visibleJobs} selectedJobId={selectedJobId} onSelectJob={selectJob} />

              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="text-xs text-slate-500">
                  Showing <span className="text-slate-300 font-medium">{visibleJobs.length}</span> of <span className="text-slate-300 font-medium">{filteredSortedJobs.length}</span>
                </div>
                {hasMore ? (
                  <button type="button" onClick={() => setVisibleCount((n) => n + 50)} className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-900" title="Client-side load more (pagination API later)">
                    Load more
                  </button>
                ) : (
                  <div className="text-xs text-slate-600">End of list</div>
                )}
              </div>
            </>
          )}
        </div>

        {/* RIGHT */}
        <div className="lg:col-span-2">
          <h1 className="text-3xl font-bold mb-4">Details</h1>

          {!selectedJob && !loadingDetails && <div className="text-slate-400">Select a job to view details</div>}

          {loadingDetails && <div className="text-sm text-slate-400">Loading job details…</div>}

          {selectedJob && !loadingDetails && (
            <div className="space-y-6">
              <JobDetailsCard job={selectedJob} onStatusChange={handleStatusChange} />

              <NotesCard notes={notes} noteText={noteText} setNoteText={setNoteText} onAddNote={handleAddNote} onDeleteNote={handleDeleteNote} />

              <DocumentsPanel jobId={selectedJob.id} onActivityChange={bumpSelectedJobActivity} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


