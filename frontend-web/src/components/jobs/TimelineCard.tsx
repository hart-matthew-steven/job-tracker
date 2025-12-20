import type { JobActivity } from "../../types/api";

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

function iconFor(type: string): string {
  const t = String(type || "").toLowerCase();
  if (t.includes("status")) return "↔";
  if (t.includes("tag")) return "🏷️";
  if (t.includes("note")) return "📝";
  if (t.includes("document")) return "📎";
  return "•";
}

type Props = {
  items: JobActivity[];
  loading?: boolean;
  error?: string;
};

export default function TimelineCard({ items, loading = false, error = "" }: Props) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xl font-semibold">Timeline</div>
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading && <div className="mt-3 text-sm text-slate-400">Loading…</div>}

      {!loading && !error && (!items || items.length === 0) && (
        <div className="mt-3 text-sm text-slate-400">No activity yet.</div>
      )}

      <div className="mt-4 space-y-3">
        {items?.map((ev) => (
          <div
            key={ev.id}
            className="rounded-lg border border-slate-800 bg-slate-950/30 px-4 py-3 flex items-start gap-3"
          >
            <div className="mt-0.5 text-slate-300 w-6 text-center">{iconFor(ev.type)}</div>
            <div className="min-w-0 flex-1">
              <div className="text-sm text-slate-100">
                {ev.message ?? ev.type}
              </div>
              <div className="mt-1 text-xs text-slate-500">{fmtDateTime(ev.created_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


