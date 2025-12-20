export const JOBS_VIEW_KEY = "jt.jobs.view";
export const SAVED_VIEW_SELECTED_KEY = "jt.jobs.savedViewId";

export type JobsViewId = "all" | "active" | "needs_followup";

export const JOBS_VIEW_OPTIONS: Array<{ value: JobsViewId; label: string }> = [
  { value: "all", label: "All" },
  { value: "active", label: "Active (not rejected)" },
  { value: "needs_followup", label: "Needs follow-up (7d+)" },
];

export const STATUS_FILTER_OPTIONS = [
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
] as const;

export type StatusFilterId = (typeof STATUS_FILTER_OPTIONS)[number]["value"];


