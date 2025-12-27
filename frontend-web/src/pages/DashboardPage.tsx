// src/pages/DashboardPage.tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";

import { listJobs } from "../api";
import type { Job } from "../types/api";
import { useToast } from "../components/ui/toast";
import { useSettings } from "../hooks/useSettings";

function startOfWeek(dateLike: string | number | Date) {
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return null;

  const day = d.getDay(); // 0=Sun
  const diff = (day === 0 ? -6 : 1) - day; // move to Monday
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function fmtWeekLabel(d: Date) {
  return d.toLocaleDateString(undefined, { month: "short", day: "2-digit" });
}

function getAppliedDate(job: Job) {
  // backend: applied_date (Date) OR created_at (DateTime)
  return job?.applied_date ?? job?.created_at ?? null;
}

// Palette (keep your current look)
const PIE_COLORS = ["#38bdf8", "#0ea5e9", "#94a3b8", "#64748b", "#475569", "#334155"];
const GRID_COLOR = "var(--chart-grid)";
const TOOLTIP_BG = "var(--chart-tooltip-bg)";
const TOOLTIP_BORDER = "var(--chart-tooltip-border)";
const TOOLTIP_TEXT = "var(--text-primary)";
const TOOLTIP_LABEL = "var(--text-muted)";
const BAR_COLOR = "var(--chart-accent)";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  const { settings } = useSettings();

  const refresh = useCallback(async () => {
    setError("");
    setLoading(true);

    try {
      const data = await listJobs(); // ✅ uses api.js helper (adds Authorization)
      const list0 = Array.isArray(data) ? (data as Job[]) : [];
      const retentionDays = Math.max(0, Number(settings?.dataRetentionDays ?? 0) || 0);
      const cutoff = retentionDays ? Date.now() - retentionDays * 24 * 60 * 60 * 1000 : 0;
      const list =
        cutoff > 0
          ? list0.filter((j) => {
              const dateLike = j.last_activity_at ?? j.applied_date ?? j.created_at ?? null;
              const t = dateLike ? new Date(dateLike).getTime() : NaN;
              if (!Number.isFinite(t)) return true;
              return t >= cutoff;
            })
          : list0;
      setJobs(list);
    } catch (e) {
      const msg = (e as { message?: string } | null)?.message ?? "Failed to load jobs";

      // If api.js logged you out (401), give a clearer hint
      if (String(msg).toLowerCase().includes("401")) {
        const m2 = "Your session expired. Please log in again.";
        setError(m2);
        toast.error(m2, "Dashboard");
      } else {
        setError(msg);
        toast.error(msg, "Dashboard");
      }

      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [settings?.dataRetentionDays, toast]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Donut: pipeline counts by status
  const pipeline = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of jobs) {
      const s = (j.status ?? "applied").toLowerCase();
      counts.set(s, (counts.get(s) ?? 0) + 1);
    }

    const preferred = ["applied", "interviewing", "offer", "rejected"];
    const entries = Array.from(counts.entries());

    entries.sort((a, b) => {
      const ia = preferred.indexOf(a[0]);
      const ib = preferred.indexOf(b[0]);
      const ra = ia === -1 ? 999 : ia;
      const rb = ib === -1 ? 999 : ib;
      return ra - rb;
    });

    return entries.map(([status, value]) => ({ status, value }));
  }, [jobs]);

  const totalJobs = jobs.length;

  // Weekly apps trend (last 10 weeks)
  const weeklyApps = useMemo(() => {
    const map = new Map<string, number>();

    for (const j of jobs) {
      const dt = getAppliedDate(j);
      if (!dt) continue;

      const weekStart = startOfWeek(dt);
      if (!weekStart) continue;

      const key = weekStart.toISOString();
      map.set(key, (map.get(key) ?? 0) + 1);
    }

    const points = Array.from(map.entries())
      .map(([iso, count]) => {
        const d = new Date(iso);
        return { iso, week: fmtWeekLabel(d), count, d };
      })
      .sort((a, b) => a.d.getTime() - b.d.getTime());

    return points.slice(-10);
  }, [jobs]);

  // KPI helpers
  const interviewingCount = useMemo(
    () => jobs.filter((j) => (j.status ?? "").toLowerCase() === "interviewing").length,
    [jobs]
  );
  const offerCount = useMemo(() => jobs.filter((j) => (j.status ?? "").toLowerCase() === "offer").length, [jobs]);
  const rejectedCount = useMemo(
    () => jobs.filter((j) => (j.status ?? "").toLowerCase() === "rejected").length,
    [jobs]
  );

  const interviewRate = totalJobs ? Math.round((interviewingCount / totalJobs) * 100) : 0;

  const hasCharts = pipeline.length > 0 || weeklyApps.length > 0;

  return (
    <div className="p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-slate-400 mt-1">Quick view of your job search pipeline.</p>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-900/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">{error}</div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs text-slate-400">Total applications</div>
          <div className="text-2xl font-bold mt-1">{totalJobs}</div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs text-slate-400">Interviewing</div>
          <div className="text-2xl font-bold mt-1">{interviewingCount}</div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs text-slate-400">Offers</div>
          <div className="text-2xl font-bold mt-1">{offerCount}</div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="text-xs text-slate-400">Interview rate</div>
          <div className="text-2xl font-bold mt-1">{interviewRate}%</div>
          <div className="text-xs text-slate-500 mt-1">(Interviewing / Total)</div>
        </div>
      </div>

      {!loading && !error && !hasCharts && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-sm text-slate-300">
          No jobs yet. Add one on the <span className="text-slate-100 font-semibold">Jobs</span> page and your dashboard will populate.
        </div>
      )}

      {/* Charts */}
      {hasCharts && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Donut pipeline */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="mb-3">
              <h2 className="text-sm font-semibold">Pipeline</h2>
              <p className="text-xs text-slate-400">Distribution by status</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pipeline} dataKey="value" nameKey="status" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
                      {pipeline.map((_, idx) => (
                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-2">
                {loading ? (
                  <div className="text-sm text-slate-400">Loading…</div>
                ) : pipeline.length === 0 ? (
                  <div className="text-sm text-slate-400">No pipeline data yet.</div>
                ) : (
                  <>
                    {pipeline.map((row, idx) => (
                      <div key={row.status} className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="h-3 w-3 rounded-sm" style={{ background: PIE_COLORS[idx % PIE_COLORS.length] }} />
                          <span className="text-sm text-slate-200 capitalize truncate">{row.status}</span>
                        </div>
                        <div className="text-sm font-semibold text-slate-100">{row.value}</div>
                      </div>
                    ))}

                    <div className="mt-3 text-xs text-slate-500">Rejected: {rejectedCount}</div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Weekly trend */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="mb-3">
              <h2 className="text-sm font-semibold">Applications over time</h2>
              <p className="text-xs text-slate-400">Last 10 weeks</p>
            </div>

            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%"> 
                <BarChart data={weeklyApps}>
                  <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
                  <XAxis dataKey="week" tick={{ fill: TOOLTIP_LABEL, fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fill: TOOLTIP_LABEL, fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${TOOLTIP_BORDER}`, color: TOOLTIP_TEXT }}
                    labelStyle={{ color: TOOLTIP_LABEL }}
                  />
                  <Bar dataKey="count" fill={BAR_COLOR} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

