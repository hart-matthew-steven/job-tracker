// src/components/documents/DocRow.jsx

function fmtDateTime(dt) {
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

function StatusBadge({ status }) {
  const s = (status ?? "").toLowerCase();
  const base =
    "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] border";

  if (s === "uploaded") {
    return (
      <span className={`${base} border-emerald-900/50 bg-emerald-950/30 text-emerald-200`}>
        Uploaded
      </span>
    );
  }

  if (s === "pending") {
    return (
      <span className={`${base} border-amber-900/50 bg-amber-950/30 text-amber-200`}>
        Pending
      </span>
    );
  }

  if (s === "scanning") {
    return (
      <span className={`${base} border-sky-900/50 bg-sky-950/30 text-sky-200`}>
        Scanning
      </span>
    );
  }

  if (s === "infected") {
    return (
      <span className={`${base} border-red-900/60 bg-red-950/30 text-red-200`}>
        Blocked
      </span>
    );
  }

  if (!status) return null;

  return (
    <span className={`${base} border-slate-700 bg-slate-900/40 text-slate-300`}>
      {status}
    </span>
  );
}

export default function DocRow({
  doc,
  onDownload,
  onDelete,
  busy = false,
  activeDocId = null,
}) {
  if (!doc) {
    return (
      <div className="text-sm text-slate-400">
        Document is missing. Try refreshing.
      </div>
    );
  }

  const created = fmtDateTime(doc.created_at);
  const status = (doc.status ?? "").toLowerCase();

  const isThisRowActive = !!busy && activeDocId === doc.id;
  const isGlobalUploadActive = !!busy && activeDocId === "upload";

  const isActive =
    isThisRowActive || (isGlobalUploadActive && (status === "pending" || !doc.status));

  const canDownload = status === "uploaded" || !doc.status;

  const disableDownload = isActive || !canDownload;
  const disableDelete = isActive;

  const showAwaiting =
    !canDownload && (status === "pending" || status === "scanning");

  const showBlocked = status === "infected";

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="text-sm font-medium text-slate-100 break-words">
          {doc.original_filename || "(unnamed file)"}
        </div>

        <div className="mt-1 text-xs text-slate-400">Uploaded: {created}</div>

        <div className="mt-2 flex items-center gap-2">
          <StatusBadge status={doc.status} />
          {isActive && <span className="text-xs text-slate-400">Working…</span>}
        </div>

        {doc.content_type && (
          <div className="mt-1 text-xs text-slate-500">{doc.content_type}</div>
        )}

        {showAwaiting && (
          <div className="mt-1 text-xs text-slate-500">
            Download available after upload is confirmed.
          </div>
        )}

        {showBlocked && (
          <div className="mt-1 text-xs text-red-200/80">
            This file was blocked by virus scanning. Please upload a clean copy.
          </div>
        )}
      </div>

      <div className="shrink-0 flex items-center gap-2">
        <button
          onClick={onDownload}
          disabled={disableDownload}
          className={[
            "rounded-md border px-3 py-1.5 text-sm transition",
            disableDownload
              ? "cursor-not-allowed border-slate-800 bg-slate-900/40 text-slate-500"
              : "cursor-pointer border-slate-700 bg-slate-800/70 hover:bg-slate-800",
          ].join(" ")}
          title={disableDownload ? "Not ready to download" : "Download"}
        >
          ⬇️
        </button>

        <button
          onClick={onDelete}
          disabled={disableDelete}
          className={[
            "rounded-md border px-3 py-1.5 text-sm transition",
            disableDelete
              ? "cursor-not-allowed border-red-950/40 bg-red-950/10 text-red-300/40"
              : "cursor-pointer border-red-900/60 bg-red-950/20 text-red-200 hover:bg-red-950/40",
          ].join(" ")}
          title="Delete"
        >
          🗑️
        </button>
      </div>
    </div>
  );
}