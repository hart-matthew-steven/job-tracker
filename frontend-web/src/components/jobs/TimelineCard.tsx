import { useEffect, useRef } from "react";

import type { JobActivity } from "../../types/api";
import CollapseToggle from "../ui/CollapseToggle";

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

function formatActivityDetails(ev: JobActivity): string | null {
  const data = ev.data;
  if (!data || typeof data !== "object") return null;
  const t = String(ev.type || "").toLowerCase();
  const safeString = (value: unknown) => {
    if (Array.isArray(value)) return value.filter(Boolean).join(", ");
    if (value === null || value === undefined) return "";
    return String(value);
  };

  if (t.includes("status")) {
    const from = safeString(data.from);
    const to = safeString(data.to);
    if (from || to) return `From ${from || "—"} → ${to || "—"}`;
  }

  if (t.includes("tag")) {
    const added = safeString(data.added);
    const removed = safeString(data.removed);
    if (added || removed) {
      return [added ? `Added: ${added}` : null, removed ? `Removed: ${removed}` : null]
        .filter(Boolean)
        .join(" • ");
    }
  }

  if (t.includes("document")) {
    const filename = safeString(data.filename);
    const docType = safeString(data.doc_type);
    return [filename && `File: ${filename}`, docType && `Type: ${docType}`].filter(Boolean).join(" • ");
  }

  if (t.includes("interview")) {
    const scheduledAt = safeString(data.scheduled_at);
    const stage = safeString(data.stage);
    const kind = safeString(data.kind);
    const interviewer = safeString(data.interviewer);
    const status = safeString(data.status);
    const changes = data.changes && typeof data.changes === "object" ? (data.changes as Record<string, unknown>) : null;
    const changeItems = changes
      ? Object.entries(changes)
          .map(([key, value]) => {
            if (!value || typeof value !== "object") return "";
            const v = value as { from?: unknown; to?: unknown };
            const from = safeString(v.from);
            const to = safeString(v.to);
            const label = key.replace(/_/g, " ");
            return from || to ? `${label}: ${from || "—"} → ${to || "—"}` : "";
          })
          .filter(Boolean)
      : [];
    const contextBits = [stage && `Stage: ${stage}`, kind && `Type: ${kind}`, interviewer && `Interviewer: ${interviewer}`, status && `Status: ${status}`]
      .filter(Boolean)
      .join(" • ");
    return [
      scheduledAt && `Scheduled: ${fmtDateTime(scheduledAt)}`,
      contextBits,
      changeItems.length ? changeItems.join(" • ") : "",
    ]
      .filter(Boolean)
      .join(" • ");
  }

  if (t.includes("note")) {
    return null;
  }

  const entries = Object.entries(data).map(([key, value]) => {
    const v = safeString(value);
    return v ? `${key}: ${v}` : "";
  });
  const fallback = entries.filter(Boolean).join(" • ");
  return fallback || null;
}

type Props = {
  items: JobActivity[];
  loading?: boolean;
  loadingMore?: boolean;
  hasMore?: boolean;
  error?: string;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onLoadMore?: () => void;
  demoMode?: boolean;
};

export default function TimelineCard({
  items,
  loading = false,
  loadingMore = false,
  hasMore = false,
  error = "",
  collapsed = false,
  onToggleCollapse,
  onLoadMore,
  demoMode = false,
}: Props) {
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = listRef.current;
    if (!node || !onLoadMore || demoMode) return;
    const handleScroll = () => {
      if (!hasMore || loadingMore) return;
      const { scrollTop, clientHeight, scrollHeight } = node;
      if (scrollHeight - (scrollTop + clientHeight) < 48) {
        onLoadMore();
      }
    };
    node.addEventListener("scroll", handleScroll);
    return () => node.removeEventListener("scroll", handleScroll);
  }, [hasMore, loadingMore, onLoadMore, demoMode]);

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xl font-semibold">Timeline</div>
        {onToggleCollapse && <CollapseToggle collapsed={collapsed} onToggle={onToggleCollapse} label="timeline section" />}
      </div>

      {!collapsed && (
        <>
          {error && (
            <div className="mt-3 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          )}

          {loading && !demoMode && <div className="mt-3 text-sm text-slate-400">Loading…</div>}

          {!loading && !error && (!items || items.length === 0) && (
            <div className="mt-3 text-sm text-slate-400">No activity yet.</div>
          )}

          <div ref={listRef} className="mt-4 space-y-3 max-h-80 overflow-y-auto pr-1">
            {items?.map((ev) => {
              const details = formatActivityDetails(ev);
              return (
                <div
                  key={ev.id}
                  className="rounded-lg border border-slate-800 bg-slate-950/30 px-4 py-3 flex items-start gap-3"
                >
                  <div className="mt-0.5 text-slate-300 w-6 text-center">{iconFor(ev.type)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-slate-100">{ev.message ?? ev.type}</div>
                    <div className="mt-1 text-xs text-slate-500">{fmtDateTime(ev.created_at)}</div>
                    {details && <div className="mt-2 text-sm text-slate-200">{details}</div>}
                  </div>
                </div>
              );
            })}
          </div>
          {loadingMore && (
            <div className="mt-2 text-xs text-slate-400 text-center">Loading older activity…</div>
          )}
          {hasMore && !loadingMore && !loading && items?.length > 0 && (
            <div className="mt-2 text-xs text-slate-500 text-center">Scroll to load older activity</div>
          )}
        </>
      )}
    </div>
  );
}


