import type { Job } from "../../types/api";

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
};

type JobWithActivity = Job & { last_activity_at?: string | null };

export default function JobDetailsCard({ job, onStatusChange }: Props) {
  if (!job) return null;
  const job2 = job as JobWithActivity;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="text-2xl font-bold">
        {job.company_name} — {job.job_title}
      </div>

      {job.location && (
        <div className="mt-2 text-slate-300 flex items-center gap-2">
          <span>📍</span>
          <span>{job.location}</span>
        </div>
      )}

      {job.job_url && (
        <div className="mt-2">
          <a
            href={job.job_url}
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
          {fmtDateTime(getAppliedDate(job))}
        </div>
        <div>
          <span className="text-slate-500">Last activity:</span>{" "}
          {fmtDateTime(job2.last_activity_at)}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <div className="text-sm text-slate-400">Status</div>

        <select
          value={(job.status ?? "applied").toLowerCase()}
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
    </div>
  );
}