// src/pages/JobsPage.tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DocumentsPanel from "../components/documents/DocumentsPanel";
import JobsList from "../components/jobs/JobsList";
import NotesCard from "../components/jobs/NotesCard";
import JobDetailsCard from "../components/jobs/JobDetailsCard";
import JobCard from "../components/jobs/JobCard";
import TimelineCard from "../components/jobs/TimelineCard";
import InterviewsCard from "../components/jobs/InterviewsCard";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/toast";
import { useCurrentUserContext } from "../context/CurrentUserContext";

import { useSettings } from "../hooks/useSettings";
import SavedViewsModal from "./jobs/SavedViewsModal";

import {
  listJobs,
  getJob,
  getJobDetails,
  createJob as apiCreateJob,
  patchJob,
  listNotes,
  addNote as apiAddNote,
  deleteNote as apiDeleteNote,
  createSavedView,
  deleteSavedView,
  listSavedViews,
  patchSavedView,
  listJobActivity,
  createInterview,
  deleteInterview,
  listInterviews,
  updateUiPreferences,
} from "../api";
import type { Job, Note, CreateJobIn, SavedView, JobActivity, JobInterview } from "../types/api";

import { JOBS_VIEW_KEY, JOBS_VIEW_OPTIONS, SAVED_VIEW_SELECTED_KEY, STATUS_FILTER_OPTIONS } from "./jobs/constants";
import type { JobsViewId, StatusFilterId } from "./jobs/constants";
import {
  hasOpenModal,
  isTypingInInput,
  jobSortKey,
  normalizeStatus,
  safeTime,
  sortJobsCompanyAsc,
  sortJobsDesc,
  sortJobsStatusAsc,
  sortNotesDesc,
} from "./jobs/utils";
import FiltersPanel from "./jobs/FiltersPanel";

const CARD_PREF_KEYS = {
  notes: "job_details_notes_collapsed",
  interviews: "job_details_interviews_collapsed",
  timeline: "job_details_timeline_collapsed",
  documents: "job_details_documents_collapsed",
} as const;

const JOBS_CACHE_KEY = "jt.jobs.cache.v1";
const SAVED_VIEWS_CACHE_KEY = "jt.saved-views.cache.v1";
const ACTIVITY_PAGE_SIZE = 20;

function readCache<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as T;
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeCache<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore
  }
}

type CardKey = keyof typeof CARD_PREF_KEYS;

export default function JobsPage() {
  const { settings, loading: settingsLoading } = useSettings();
  const toast = useToast();
  const { user: currentUser, reload: reloadCurrentUser } = useCurrentUserContext();
  const [jobs, setJobs] = useState<Job[]>(() => readCache<Job[]>(JOBS_CACHE_KEY, []));
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [collapsedCards, setCollapsedCards] = useState<Record<CardKey, boolean>>({
    notes: Boolean(currentUser?.ui_preferences?.[CARD_PREF_KEYS.notes]),
    interviews: Boolean(currentUser?.ui_preferences?.[CARD_PREF_KEYS.interviews]),
    timeline: Boolean(currentUser?.ui_preferences?.[CARD_PREF_KEYS.timeline]),
    documents: Boolean(currentUser?.ui_preferences?.[CARD_PREF_KEYS.documents]),
  });

  useEffect(() => {
    const prefs = currentUser?.ui_preferences ?? {};
    setCollapsedCards({
      notes: Boolean(prefs[CARD_PREF_KEYS.notes]),
      interviews: Boolean(prefs[CARD_PREF_KEYS.interviews]),
      timeline: Boolean(prefs[CARD_PREF_KEYS.timeline]),
      documents: Boolean(prefs[CARD_PREF_KEYS.documents]),
    });
  }, [currentUser?.ui_preferences]);

  const persistCollapsePreference = useCallback(
    async (key: CardKey, nextState: boolean) => {
      const prefKey = CARD_PREF_KEYS[key];
      try {
        await updateUiPreferences({ preferences: { [prefKey]: nextState } });
        await reloadCurrentUser();
      } catch (err) {
        const message = (err as { message?: string } | null)?.message ?? "Failed to save panel preference.";
        toast.error(message, "Preferences");
        setCollapsedCards((prev) => ({ ...prev, [key]: !nextState }));
      }
    },
    [reloadCurrentUser, toast]
  );

  const persistPreferenceRef = useRef(persistCollapsePreference);
  useEffect(() => {
    persistPreferenceRef.current = persistCollapsePreference;
  }, [persistCollapsePreference]);

  const toggleCard = (key: CardKey) => {
    setCollapsedCards((prev) => {
      const nextState = !prev[key];
      queueMicrotask(() => {
        persistPreferenceRef.current?.(key, nextState);
      });
      return { ...prev, [key]: nextState };
    });
  };


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
  const [loadingJobs, setLoadingJobs] = useState(jobs.length === 0);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);

  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState("updated_desc");
  const [visibleCount, setVisibleCount] = useState(50);
  const [tagQuery, setTagQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedStatuses, setSelectedStatuses] = useState<StatusFilterId[]>([]);
  const [tagFilterOpen, setTagFilterOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [viewsOpen, setViewsOpen] = useState(false);
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => readCache<SavedView[]>(SAVED_VIEWS_CACHE_KEY, []));
  const [viewsBusy, setViewsBusy] = useState(savedViews.length === 0);
  const [saveName, setSaveName] = useState("");
  const [selectedSavedViewId, setSelectedSavedViewId] = useState<number | null>(() => {
    try {
      const raw = localStorage.getItem(SAVED_VIEW_SELECTED_KEY);
      const n = raw ? Number(raw) : 0;
      return Number.isFinite(n) && n > 0 ? n : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      if (!selectedSavedViewId) localStorage.removeItem(SAVED_VIEW_SELECTED_KEY);
      else localStorage.setItem(SAVED_VIEW_SELECTED_KEY, String(selectedSavedViewId));
    } catch {
      // ignore
    }
  }, [selectedSavedViewId]);
  const [view, setView] = useState<JobsViewId>(() => {
    try {
      const raw = localStorage.getItem(JOBS_VIEW_KEY);
      const v = (raw || "").trim() as JobsViewId;
      if (JOBS_VIEW_OPTIONS.some((o) => o.value === v)) return v;
    } catch {
      // ignore
    }
    return "all";
  });

  // Apply user defaults once (only if user hasn't already chosen values).
  const appliedDefaultsRef = useRef(false);
  useEffect(() => {
    if (appliedDefaultsRef.current) return;
    if (settingsLoading) return;
    const defaultSort = String(settings.defaultJobsSort ?? "").trim();
    const defaultView = String(settings.defaultJobsView ?? "").trim().toLowerCase();

    if (defaultSort && sortMode === "updated_desc") {
      setSortMode(defaultSort);
    }

    // Only apply default view if localStorage didn't already set it.
    try {
      const existing = localStorage.getItem(JOBS_VIEW_KEY);
      if (!existing && defaultView && JOBS_VIEW_OPTIONS.some((o) => o.value === (defaultView as JobsViewId))) {
        setView(defaultView as JobsViewId);
      }
    } catch {
      // ignore
    }

    appliedDefaultsRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsLoading, settings.defaultJobsSort, settings.defaultJobsView]);

  useEffect(() => {
    try {
      localStorage.setItem(JOBS_VIEW_KEY, view);
    } catch {
      // ignore
    }
  }, [view]);

  const selectedJobId = useMemo(() => selectedJob?.id ?? null, [selectedJob]);
  const [activity, setActivity] = useState<JobActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [activityError, setActivityError] = useState("");
  const [activityCursor, setActivityCursor] = useState<number | null>(null);
  const [loadingMoreActivity, setLoadingMoreActivity] = useState(false);
  const loadingMoreActivityRef = useRef(false);

  const [interviews, setInterviews] = useState<JobInterview[]>([]);
  const [loadingInterviews, setLoadingInterviews] = useState(false);
  const [interviewsError, setInterviewsError] = useState("");

  // Prevent out-of-order responses when clicking jobs quickly
  const selectSeqRef = useRef(0);
  const refreshSeqRef = useRef(0);
  const refreshJobsRef = useRef<(opts?: { source?: string }) => void>(() => { });

  const initialLoadDoneRef = useRef(false);
  useEffect(() => {
    if (initialLoadDoneRef.current) return;
    initialLoadDoneRef.current = true;
    refreshJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  refreshJobsRef.current = refreshJobs;

  // Refetch when filters change (debounced) so server-side filtering feels instant.
  const filterTimerRef = useRef<number | null>(null);
  const filtersInitializedRef = useRef(false);
  useEffect(() => {
    if (!filtersInitializedRef.current) {
      filtersInitializedRef.current = true;
      return;
    }
    if (filterTimerRef.current) window.clearTimeout(filterTimerRef.current);
    filterTimerRef.current = window.setTimeout(() => {
      refreshJobsRef.current?.({ source: "filter" });
    }, 250);
    return () => {
      if (filterTimerRef.current) window.clearTimeout(filterTimerRef.current);
    };
  }, [search, tagQuery, selectedTags, selectedStatuses]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (savedViews.length === 0) setViewsBusy(true);
      try {
        const list = await listSavedViews();
        if (cancelled) return;
        const next = Array.isArray(list) ? list : [];
        setSavedViews(next);
        writeCache(SAVED_VIEWS_CACHE_KEY, next);
      } catch (e) {
        if (cancelled) return;
        const msg = (e as { message?: string } | null)?.message ?? "Failed to load saved views";
        toast.error(msg, "Saved views");
      } finally {
        if (!cancelled) setViewsBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      const data = await listJobs({
        q: search,
        tag_q: tagQuery,
        tag: selectedTags,
        status: selectedStatuses,
      });
      const list0 = Array.isArray(data) ? (data as Job[]) : [];
      const retentionDays = Math.max(0, Number(settings?.dataRetentionDays ?? 0) || 0);
      const cutoff = retentionDays ? Date.now() - retentionDays * 24 * 60 * 60 * 1000 : 0;
      const list =
        cutoff > 0
          ? list0.filter((j) => {
            const t = safeTime(jobSortKey(j));
            // If we can't parse a time, keep it visible.
            if (!Number.isFinite(t)) return true;
            return t >= cutoff;
          })
          : list0;
      if (refreshSeqRef.current !== mySeq) return;
      const sorted = sortJobsDesc(list);
      setJobs(sorted);
      writeCache(JOBS_CACHE_KEY, sorted);
      setLastUpdatedAt(new Date());

      if (selectedJobId && !list.some((j) => j.id === selectedJobId)) {
        setSelectedJob(null);
        setNotes([]);
      }
    } catch (e) {
      if (refreshSeqRef.current !== mySeq) return;
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load jobs";
      setError(msg);
      toast.error(msg, "Jobs");
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
      const sorted = sortJobsDesc(next);
      writeCache(JOBS_CACHE_KEY, sorted);
      return sorted;
    });
  }

  const statusCounts = useMemo(() => {
    const counts: Record<StatusFilterId, number> = {
      applied: 0,
      interviewing: 0,
      offer: 0,
      rejected: 0,
    };
    for (const j of jobs) {
      const s = normalizeStatus(j) as StatusFilterId;
      if (s in counts) counts[s] += 1;
    }
    return counts;
  }, [jobs]);

  const viewCounts = useMemo<Record<JobsViewId, number>>(() => {
    const now = Date.now();
    const followupCutoffMs = 7 * 24 * 60 * 60 * 1000;

    return {
      all: jobs.length,
      active: jobs.filter((j) => normalizeStatus(j) !== "rejected").length,
      needs_followup: jobs.filter((j) => {
        const status = normalizeStatus(j);
        if (status === "rejected") return false;
        const t = safeTime(jobSortKey(j));
        if (!t) return true;
        return now - t >= followupCutoffMs;
      }).length,
    };
  }, [jobs]);

  const tagSuggestions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs) {
      const tags = Array.isArray(j.tags) ? j.tags : [];
      for (const raw of tags) {
        const t = String(raw ?? "").trim().toLowerCase();
        if (!t) continue;
        counts.set(t, (counts.get(t) ?? 0) + 1);
      }
    }

    const q = String(tagQuery ?? "").trim().toLowerCase();
    const list = Array.from(counts.entries())
      .filter(([t]) => (q ? t.includes(q) : true))
      .sort((a, b) => {
        const byCount = (b[1] ?? 0) - (a[1] ?? 0);
        if (byCount !== 0) return byCount;
        return a[0].localeCompare(b[0]);
      })
      .map(([t]) => t);

    return list.slice(0, q ? 10 : 12);
  }, [jobs, tagQuery]);

  function getCurrentViewData(): Record<string, unknown> {
    return {
      search,
      tagQuery,
      tags: selectedTags,
      statuses: selectedStatuses,
      view,
      sortMode,
    };
  }

  function applySavedViewData(data: Record<string, unknown> | null | undefined) {
    const d = data ?? {};
    const s = typeof d.search === "string" ? d.search : "";
    const tf =
      typeof (d as Record<string, unknown>).tagQuery === "string"
        ? ((d as Record<string, unknown>).tagQuery as string)
        : typeof (d as Record<string, unknown>).tagFilter === "string"
          ? ((d as Record<string, unknown>).tagFilter as string)
          : "";
    const tags =
      Array.isArray((d as Record<string, unknown>).tags)
        ? ((d as Record<string, unknown>).tags as unknown[])
          .map((x) => String(x ?? "").trim().toLowerCase())
          .filter(Boolean)
        : [];
    const statuses =
      Array.isArray((d as Record<string, unknown>).statuses)
        ? ((d as Record<string, unknown>).statuses as unknown[])
          .map((x) => String(x ?? "").trim().toLowerCase())
          .filter((x) => STATUS_FILTER_OPTIONS.some((o) => o.value === x)) as StatusFilterId[]
        : [];
    const sm = typeof d.sortMode === "string" ? d.sortMode : "updated_desc";
    const vRaw = typeof d.view === "string" ? (d.view as JobsViewId) : "all";
    const vNext = JOBS_VIEW_OPTIONS.some((o) => o.value === vRaw) ? vRaw : "all";

    setSearch(s);
    setTagQuery(tf);
    setSelectedTags(tags);
    setSelectedStatuses(statuses);
    setSortMode(sm);
    setView(vNext);
    setVisibleCount(50);
  }

  function handleSaveCurrentView() {
    void (async () => {
      const name = saveName.trim();
      if (!name) {
        toast.error("Missing view name.", "Saved views");
        return;
      }
      setViewsBusy(true);
      try {
        const data = getCurrentViewData();
        const created = await createSavedView({ name, data });
        setSavedViews((prev) => {
          const next = [created, ...prev];
          writeCache(SAVED_VIEWS_CACHE_KEY, next);
          return next;
        });
        setSelectedSavedViewId(created.id);
        toast.success("Saved view created.", "Saved views");
        setSaveName("");
      } catch (e) {
        const msg = (e as { message?: string } | null)?.message ?? "Failed to save view";
        // If name already exists, overwrite the existing one (nice UX).
        if (String(msg).toLowerCase().includes("already exists")) {
          const existing = savedViews.find((v) => v.name === name);
          if (existing) {
            try {
              const updated = await patchSavedView(existing.id, { data: getCurrentViewData() });
              setSavedViews((prev) => {
                const next = prev.map((v) => (v.id === updated.id ? updated : v));
                writeCache(SAVED_VIEWS_CACHE_KEY, next);
                return next;
              });
              setSelectedSavedViewId(updated.id);
              toast.success("Saved view updated.", "Saved views");
              setSaveName("");
              return;
            } catch (e2) {
              const msg2 = (e2 as { message?: string } | null)?.message ?? "Failed to update view";
              toast.error(msg2, "Saved views");
              return;
            }
          }
        }
        toast.error(msg, "Saved views");
      } finally {
        setViewsBusy(false);
      }
    })();
  }

  function handleApplySavedView(sv: SavedView) {
    setSelectedSavedViewId(sv.id);
    applySavedViewData(sv.data);
    toast.info(`Applied "${sv.name}".`, "Saved views");
    setViewsOpen(false);
  }

  function handleDeleteSavedView(sv: SavedView) {
    void (async () => {
      setViewsBusy(true);
      try {
        await deleteSavedView(sv.id);
        setSavedViews((prev) => {
          const next = prev.filter((v) => v.id !== sv.id);
          writeCache(SAVED_VIEWS_CACHE_KEY, next);
          return next;
        });
        if (selectedSavedViewId === sv.id) setSelectedSavedViewId(null);
        toast.success("Saved view deleted.", "Saved views");
      } catch (e) {
        const msg = (e as { message?: string } | null)?.message ?? "Failed to delete view";
        toast.error(msg, "Saved views");
      } finally {
        setViewsBusy(false);
      }
    })();
  }

  const filteredSortedJobs = useMemo(() => {
    const now = Date.now();
    const followupCutoffMs = 7 * 24 * 60 * 60 * 1000;

    const filtered = jobs.filter((j) => {
      const status = normalizeStatus(j);
      if (view === "all") return true;
      if (view === "active") return status !== "rejected";
      if (view === "needs_followup") {
        if (status === "rejected") return false;
        const t = safeTime(jobSortKey(j));
        if (!t) return true;
        return now - t >= followupCutoffMs;
      }
      return status === view;
    });

    if (sortMode === "company_asc") return sortJobsCompanyAsc(filtered);
    if (sortMode === "status_asc") return sortJobsStatusAsc(filtered);
    return sortJobsDesc(filtered);
  }, [jobs, sortMode, view]);

  const visibleJobs = useMemo(() => filteredSortedJobs.slice(0, visibleCount), [filteredSortedJobs, visibleCount]);

  const hasMore = visibleJobs.length < filteredSortedJobs.length;

  async function selectJob(job: Job) {
    if (!job?.id) return;

    setError("");
    setLoadingDetails(true);
    setLoadingInterviews(true);
    setLoadingActivity(true);
    setInterviewsError("");
    setActivityError("");

    const mySeq = ++selectSeqRef.current;

    try {
      const bundle = await getJobDetails(job.id, { activity_limit: ACTIVITY_PAGE_SIZE });
      if (selectSeqRef.current !== mySeq) return;

      const freshJob = bundle?.job ?? (await getJob(job.id));

      setSelectedJob(freshJob);
      upsertJob(freshJob);
      setNotes(sortNotesDesc(Array.isArray(bundle?.notes) ? (bundle?.notes as Note[]) : []));
      setInterviews(Array.isArray(bundle?.interviews) ? bundle?.interviews : []);
      const activityPage = bundle?.activity ?? { items: [], next_cursor: null };
      setActivity(Array.isArray(activityPage?.items) ? activityPage.items : []);
      setActivityCursor(activityPage?.next_cursor ?? null);
    } catch (e) {
      if (selectSeqRef.current !== mySeq) return;
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load job details";
      setError(msg);
      toast.error(msg, "Job details");
    } finally {
      if (selectSeqRef.current === mySeq) {
        setLoadingDetails(false);
        setLoadingInterviews(false);
        setLoadingActivity(false);
      }
    }
  }

  async function refreshActivity() {
    if (!selectedJob?.id) return;
    setLoadingActivity(true);
    setActivityError("");
    try {
      const page = await listJobActivity(selectedJob.id, { limit: ACTIVITY_PAGE_SIZE });
      setActivity(Array.isArray(page?.items) ? page.items : []);
      setActivityCursor(page?.next_cursor ?? null);
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load timeline";
      setActivityError(msg);
      toast.error(msg, "Timeline");
    } finally {
      setLoadingActivity(false);
    }
  }

  const loadMoreActivity = useCallback(async () => {
    if (!selectedJob?.id) return;
    if (!activityCursor) return;
    if (loadingMoreActivityRef.current || loadingMoreActivity || loadingActivity) return;
    loadingMoreActivityRef.current = true;
    setActivityError("");
    setLoadingMoreActivity(true);
    try {
      const page = await listJobActivity(selectedJob.id, {
        limit: ACTIVITY_PAGE_SIZE,
        cursor_id: activityCursor,
      });
      setActivity((prev) => [...prev, ...(Array.isArray(page?.items) ? page.items : [])]);
      setActivityCursor(page?.next_cursor ?? null);
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load timeline";
      setActivityError(msg);
      toast.error(msg, "Timeline");
    } finally {
      loadingMoreActivityRef.current = false;
      setLoadingMoreActivity(false);
    }
  }, [selectedJob?.id, activityCursor, loadingMoreActivity, loadingActivity, toast]);

  async function refreshInterviews() {
    if (!selectedJob?.id) return;
    setLoadingInterviews(true);
    setInterviewsError("");
    try {
      const ivs = await listInterviews(selectedJob.id);
      setInterviews(Array.isArray(ivs) ? ivs : []);
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load interviews";
      setInterviewsError(msg);
      toast.error(msg, "Interviews");
    } finally {
      setLoadingInterviews(false);
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
      const msg = "Company name and job title are required.";
      setError(msg);
      toast.error(msg, "Add job");
      return;
    }

    try {
      const created = await apiCreateJob(payload);

      setForm({ company_name: "", job_title: "", location: "", job_url: "" });

      upsertJob(created);

      await selectJob(created);
      setAddOpen(false);
      toast.success("Job created.", "Add job");
    } catch (e2) {
      const msg = (e2 as { message?: string } | null)?.message ?? "Failed to create job";
      setError(msg);
      toast.error(msg, "Add job");
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
      toast.success("Note added.", "Notes");
      void refreshActivity();
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to add note";
      setError(msg);
      toast.error(msg, "Notes");
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
      toast.success("Note deleted.", "Notes");
      void refreshActivity();
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to delete note";
      setError(msg);
      toast.error(msg, "Notes");
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!selectedJob) return;
    setError("");

    try {
      const updated = await patchJob(selectedJob.id, { status: newStatus });
      setSelectedJob(updated);
      upsertJob(updated);
      void refreshActivity();
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to update status";
      setError(msg);
      toast.error(msg, "Status");
    }
  }

  async function handleTagsChange(nextTags: string[]) {
    if (!selectedJob) return;
    setError("");
    try {
      const updated = await patchJob(selectedJob.id, { tags: nextTags });
      setSelectedJob(updated);
      upsertJob(updated);
      toast.success("Tags updated.", "Tags");
      void refreshActivity();
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to update tags";
      setError(msg);
      toast.error(msg, "Tags");
    }
  }

  function bumpSelectedJobActivity(iso: string) {
    if (!selectedJob) return;

    setSelectedJob((prev) => (prev ? { ...prev, last_activity_at: iso } : prev));

    setJobs((prev) => {
      const next = prev.map((j) => (j.id === selectedJob.id ? { ...j, last_activity_at: iso } : j));
      const sorted = sortJobsDesc(next);
      writeCache(JOBS_CACHE_KEY, sorted);
      return sorted;
    });
  }

  return (
    <div className="p-8">
      {error && (
        <div className="mb-6 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
          <div className="mt-2 text-xs text-slate-700 dark:text-slate-300">
            If this happened right after login, your session may have expired — try logging in again.
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[520px_1fr] gap-8">
        {/* LEFT */}
        <div>
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h1 className="text-3xl font-bold">Jobs</h1>
              <div className="mt-1 text-xs text-slate-500">
                {lastUpdatedAt ? (
                  <>
                    Last updated{" "}
                    <span className="text-slate-700 dark:text-slate-300 font-medium">
                      {lastUpdatedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </>
                ) : (
                  " "
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {loadingJobs && <div className="text-xs text-slate-400">Refreshing…</div>}
              <button
                type="button"
                onClick={() => {
                  // Apply account defaults (and clear any ad-hoc filters).
                  setSearch("");
                  setTagQuery("");
                  setSelectedTags([]);
                  setSelectedStatuses([]);
                  setSortMode(settings.defaultJobsSort || "updated_desc");
                  const dv = String(settings.defaultJobsView || "all").toLowerCase();
                  setView(JOBS_VIEW_OPTIONS.some((o) => o.value === (dv as JobsViewId)) ? (dv as JobsViewId) : "all");
                  setVisibleCount(50);
                  toast.success("Applied account defaults.", "Jobs");
                }}
                className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-200 dark:hover:bg-slate-900"
                title="Apply your account default Jobs settings"
              >
                Use defaults
              </button>
              <button
                type="button"
                onClick={() => setViewsOpen(true)}
                className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900"
                title="Manage saved views"
              >
                Views
              </button>
              <button
                type="button"
                onClick={() => setAddOpen(true)}
                className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900"
                title="Add a new job"
              >
                + Add job
              </button>
            </div>
          </div>

          <div className="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Search</label>
              <input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setVisibleCount(50);
                }}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400"
                placeholder="Company, title, location…"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Sort</label>
              <select
                value={sortMode}
                onChange={(e) => setSortMode(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-600/30 dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100"
              >
                <option value="updated_desc">Updated (desc)</option>
                <option value="company_asc">Company (A→Z)</option>
                <option value="status_asc">Status</option>
              </select>
            </div>
          </div>

          <FiltersPanel
            selectedTags={selectedTags}
            onRemoveTag={(t) => {
              setSelectedTags((prev) => prev.filter((x) => x !== t));
              setVisibleCount(50);
            }}
            tagQuery={tagQuery}
            onTagQueryChange={(next) => {
              setTagQuery(next);
              setVisibleCount(50);
            }}
            tagSuggestions={tagSuggestions}
            tagFilterOpen={tagFilterOpen}
            onTagFilterOpenChange={setTagFilterOpen}
            onSelectTagSuggestion={(t) => {
              setSelectedTags((prev) => (prev.includes(t) ? prev : [...prev, t]));
              setTagQuery("");
              setVisibleCount(50);
              setTagFilterOpen(false);
              setView("all");
            }}
            onClearTagFilter={() => {
              setTagQuery("");
              setSelectedTags([]);
              setVisibleCount(50);
            }}
            view={view}
            viewCounts={viewCounts}
            onSelectView={(v) => {
              setView(v);
              setSelectedStatuses([]);
              setVisibleCount(50);
            }}
            selectedStatuses={selectedStatuses}
            statusCounts={statusCounts}
            onToggleStatus={(status) => {
              setView("all");
              setSelectedStatuses((prev) => (prev.includes(status) ? prev.filter((x) => x !== status) : [...prev, status]));
              setVisibleCount(50);
            }}
          />

          <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add job">
            <JobCard form={form} setForm={setForm} onCreateJob={handleCreateJob} title={null} className="mb-0 border-0 bg-transparent p-0" />
          </Modal>

          <SavedViewsModal
            open={viewsOpen}
            onClose={() => setViewsOpen(false)}
            viewsBusy={viewsBusy}
            saveName={saveName}
            onSaveNameChange={setSaveName}
            onSave={handleSaveCurrentView}
            savedViews={savedViews}
            selectedSavedViewId={selectedSavedViewId}
            onApply={handleApplySavedView}
            onDelete={handleDeleteSavedView}
          />

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
                  <button type="button" onClick={() => setVisibleCount((n) => n + 50)} className="rounded-lg px-3 py-2 text-xs font-semibold transition border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900" title="Client-side load more (pagination API later)">
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
        <div>
          <h1 className="text-3xl font-bold mb-4">Details</h1>

          {!selectedJob && !loadingDetails && <div className="text-slate-400">Select a job to view details</div>}

          {loadingDetails && <div className="text-sm text-slate-400">Loading job details…</div>}

          {selectedJob && !loadingDetails && (
            <div className="space-y-6">
              <JobDetailsCard job={selectedJob} onStatusChange={handleStatusChange} onTagsChange={handleTagsChange} />

              <NotesCard
                notes={notes}
                noteText={noteText}
                setNoteText={setNoteText}
                onAddNote={handleAddNote}
                onDeleteNote={handleDeleteNote}
                collapsed={collapsedCards.notes}
                onToggleCollapse={() => toggleCard("notes")}
              />

              <InterviewsCard
                items={interviews}
                loading={loadingInterviews}
                error={interviewsError}
                collapsed={collapsedCards.interviews}
                onToggleCollapse={() => toggleCard("interviews")}
                onCreate={async (draft) => {
                  if (!selectedJob) return;
                  try {
                    await createInterview(selectedJob.id, {
                      scheduled_at: draft.scheduled_at,
                      stage: draft.stage || null,
                      kind: draft.kind || null,
                      location: draft.location || null,
                      interviewer: draft.interviewer || null,
                      status: draft.status || "scheduled",
                      notes: draft.notes || null,
                    });
                    toast.success("Interview added.", "Interviews");
                    await refreshInterviews();
                    await refreshActivity();
                  } catch (e) {
                    const msg = (e as { message?: string } | null)?.message ?? "Failed to add interview";
                    toast.error(msg, "Interviews");
                  }
                }}
                onDelete={async (id) => {
                  if (!selectedJob) return;
                  try {
                    await deleteInterview(selectedJob.id, id);
                    toast.success("Interview deleted.", "Interviews");
                    await refreshInterviews();
                    await refreshActivity();
                  } catch (e) {
                    const msg = (e as { message?: string } | null)?.message ?? "Failed to delete interview";
                    toast.error(msg, "Interviews");
                  }
                }}
              />

              <TimelineCard
                items={activity}
                loading={loadingActivity}
                loadingMore={loadingMoreActivity}
                hasMore={Boolean(activityCursor)}
                onLoadMore={loadMoreActivity}
                error={activityError}
                collapsed={collapsedCards.timeline}
                onToggleCollapse={() => toggleCard("timeline")}
              />

              <DocumentsPanel
                jobId={selectedJob.id}
                collapsed={collapsedCards.documents}
                onToggleCollapse={() => toggleCard("documents")}
                onActivityChange={(iso) => {
                  bumpSelectedJobActivity(iso);
                  void refreshActivity();
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


