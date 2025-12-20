import type { Job } from "../../types/api";
import { useMemo, useState } from "react";

const STATUS_OPTIONS = [
  { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
];

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

function getAppliedDate(job: Job) {
  return job?.applied_date ?? job?.created_at ?? null;
}

type Props = {
  job: Job | null;
  onStatusChange?: (nextStatus: string) => void;
  onTagsChange?: (nextTags: string[]) => Promise<void> | void;
};

type JobWithActivity = Job & { last_activity_at?: string | null };

function normalizeTag(raw: unknown): string {
  const s = String(raw ?? "").trim().toLowerCase();
  if (!s) return "";
  return s.length > 64 ? s.slice(0, 64) : s;
}

export default function JobDetailsCard({ job, onStatusChange, onTagsChange }: Props) {
  const job2 = job as JobWithActivity | null;

  const tags = useMemo(() => {
    if (!job2) return [];
    const raw = Array.isArray(job2.tags) ? job2.tags : [];
    const out: string[] = [];
    for (const t of raw) {
      const s = normalizeTag(t);
      if (!s) continue;
      if (!out.includes(s)) out.push(s);
    }
    return out;
  }, [job2]);

  const [tagText, setTagText] = useState("");
  const [tagsBusy, setTagsBusy] = useState(false);

  if (!job2) return null;

  async function addTag() {
    if (!onTagsChange) return;
    const next = normalizeTag(tagText);
    if (!next) return;
    if (tags.includes(next)) {
      setTagText("");
      return;
    }
    setTagsBusy(true);
    try {
      await onTagsChange([...tags, next]);
      setTagText("");
    } finally {
      setTagsBusy(false);
    }
  }

  async function removeTag(tag: string) {
    if (!onTagsChange) return;
    const nextTags = tags.filter((t) => t !== tag);
    setTagsBusy(true);
    try {
      await onTagsChange(nextTags);
    } finally {
      setTagsBusy(false);
    }
  }

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="text-2xl font-bold">
        {job2.company_name} — {job2.job_title}
      </div>

      {job2.location && (
        <div className="mt-2 text-slate-300 flex items-center gap-2">
          <span>📍</span>
          <span>{job2.location}</span>
        </div>
      )}

      {job2.job_url && (
        <div className="mt-2">
          <a
            href={job2.job_url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-400 hover:text-blue-300 underline cursor-pointer"
          >
            Job Link
          </a>
        </div>
      )}

      <div className="mt-4 text-sm text-slate-300 flex flex-wrap gap-x-6 gap-y-1">
        <div>
          <span className="text-slate-500">Applied:</span>{" "}
          {fmtDateTime(getAppliedDate(job2))}
        </div>
        <div>
          <span className="text-slate-500">Last activity:</span>{" "}
          {fmtDateTime(job2.last_activity_at)}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <div className="text-sm text-slate-400">Status</div>

        <select
          value={(job2.status ?? "applied").toLowerCase()}
          onChange={(e) => onStatusChange?.(e.target.value)}
          className="rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-500 cursor-pointer"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-5">
        <div className="text-sm text-slate-400 mb-2">Tags</div>

        <div className="flex flex-wrap gap-2">
          {tags.length === 0 ? (
            <div className="text-xs text-slate-500">No tags yet.</div>
          ) : (
            tags.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => removeTag(t)}
                disabled={!onTagsChange || tagsBusy}
                className={[
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                  !onTagsChange || tagsBusy
                    ? "cursor-not-allowed border-slate-800 bg-slate-950/30 text-slate-500"
                    : "cursor-pointer border-slate-700 bg-slate-800/50 text-slate-200 hover:bg-slate-800",
                ].join(" ")}
                title="Remove tag"
              >
                <span className="truncate max-w-[12rem]">{t}</span>
                <span className="text-slate-400" aria-hidden="true">
                  ✕
                </span>
              </button>
            ))
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <input
            value={tagText}
            onChange={(e) => setTagText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addTag();
            }}
            disabled={!onTagsChange || tagsBusy}
            className="flex-1 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-600/30"
            placeholder="Add tag (e.g. referral, remote, follow-up)"
          />
          <button
            type="button"
            onClick={addTag}
            disabled={!onTagsChange || tagsBusy}
            className={[
              "rounded-lg px-3 py-2 text-xs font-semibold transition border",
              !onTagsChange || tagsBusy
                ? "cursor-not-allowed border-slate-800 bg-slate-900/40 text-slate-500"
                : "border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-900",
            ].join(" ")}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}