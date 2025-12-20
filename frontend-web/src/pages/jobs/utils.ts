import type { Job, Note } from "../../types/api";

export function normalizeStatus(job: Job): string {
  const s = String(job?.status ?? "applied").trim().toLowerCase();
  return s || "applied";
}

export function jobSortKey(job: Job | null | undefined) {
  return job?.last_activity_at ?? job?.applied_date ?? job?.created_at ?? null;
}

export function safeTime(value: string | null | undefined) {
  const t = new Date(value ?? 0).getTime();
  return Number.isNaN(t) ? 0 : t;
}

export function sortJobsDesc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) => safeTime(jobSortKey(b)) - safeTime(jobSortKey(a)));
  return copy;
}

export function sortNotesDesc(list: Note[]) {
  const copy = [...list];
  copy.sort((a, b) => safeTime(b?.created_at) - safeTime(a?.created_at));
  return copy;
}

export function sortJobsCompanyAsc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) =>
    String(a?.company_name ?? "").localeCompare(String(b?.company_name ?? ""), undefined, {
      sensitivity: "base",
    })
  );
  return copy;
}

export function sortJobsStatusAsc(list: Job[]) {
  const copy = [...list];
  copy.sort((a, b) =>
    String(a?.status ?? "").localeCompare(String(b?.status ?? ""), undefined, {
      sensitivity: "base",
    })
  );
  return copy;
}

export function matchesJob(job: Job, q: string) {
  const query = String(q ?? "").trim().toLowerCase();
  if (!query) return true;

  const hay = [job?.company_name, job?.job_title, job?.location].filter(Boolean).join(" ").toLowerCase();
  return hay.includes(query);
}

export function hasOpenModal() {
  return Boolean(document.querySelector('dialog[open], [role="dialog"], [aria-modal="true"], [data-modal="true"]'));
}

export function isTypingInInput() {
  const el = document.activeElement;
  if (!el) return false;
  if ((el as HTMLElement).isContentEditable) return true;

  const tag = String((el as Element).tagName ?? "").toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}


