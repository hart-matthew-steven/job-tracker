import type { Job } from "../../types/api";

type JobWithActivity = Job & { last_activity_at?: string | null };

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

function jobSortKey(job: JobWithActivity) {
  return job?.last_activity_at ?? job?.applied_date ?? job?.created_at ?? null;
}

function getActivityDotColor(iso: string | null | undefined) {
  if (!iso) return "bg-slate-500";

  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffHours = (now - then) / (1000 * 60 * 60);

  if (diffHours <= 48) return "bg-green-500";
  if (diffHours <= 168) return "bg-yellow-500";
  return "bg-red-500";
}

type Props = {
  jobs: JobWithActivity[];
  selectedJobId: number | null;
  onSelectJob: (job: JobWithActivity) => void;
};

export default function JobsList({ jobs, selectedJobId, onSelectJob }: Props) {
  return (
    <div className="space-y-3">
      {jobs.map((job) => {
        const isSelected = selectedJobId === job.id;
        const lastActivity = jobSortKey(job);
        const dotColor = getActivityDotColor(lastActivity);

        return (
          <button
            key={job.id}
            onClick={() => onSelectJob(job)}
            className={[
              "w-full text-left rounded-xl border px-4 py-4 transition cursor-pointer",
              isSelected
                ? "bg-slate-800/80 border-slate-600"
                : "bg-slate-900/50 border-slate-800 hover:bg-slate-900/80",
            ].join(" ")}
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2.5 w-2.5 rounded-full ${dotColor} animate-pulse`}
                title="Last activity indicator"
              />
              <span className="font-semibold">
                {job.company_name} — {job.job_title}
              </span>
            </div>

            {job.last_activity_at && (
              <div className="mt-2 text-xs text-slate-400">
                <span className="text-slate-500">Last activity:</span>{" "}
                {fmtDateTime(job.last_activity_at)}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}