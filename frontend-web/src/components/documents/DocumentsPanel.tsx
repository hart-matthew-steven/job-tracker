// src/components/documents/DocumentsPanel.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import {
  deleteDocument,
  listDocuments,
  presignDocumentDownload,
  presignDocumentUpload,
  uploadToS3PresignedUrl,
  confirmDocumentUpload,
} from "../../api";

import DocumentSection from "./DocumentSection";
import DocRow from "./DocRow";

type DocType = { key: string; label: string; multiple: boolean };

type Doc = {
  id: number;
  doc_type?: string | null;
  original_filename?: string | null;
  content_type?: string | null;
  status?: string | null;
  created_at?: string | null;
};

const DOC_TYPES = [
  { key: "resume", label: "Resume", multiple: false },
  { key: "job_description", label: "Job Description", multiple: false },
  { key: "cover_letter", label: "Cover Letter", multiple: false },
  { key: "thank_you", label: "Thank You Letters", multiple: true },
] as const satisfies readonly DocType[];

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;

function safeTime(value: string | null | undefined) {
  const t = new Date(value ?? 0).getTime();
  return Number.isNaN(t) ? 0 : t;
}

type Props = {
  jobId: number | null;
  onActivityChange?: (iso: string) => void;
};

export default function DocumentsPanel({ jobId, onActivityChange }: Props) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [inputKey, setInputKey] = useState(0);
  const [activeDocId, setActiveDocId] = useState<number | null>(null);

  // Prevent stale refresh() results when switching jobs quickly
  const refreshSeqRef = useRef(0);

  useEffect(() => {
    if (!jobId) return;

    // reset per-job UI state so it doesn't leak between jobs
    setDocs([]);
    setBusy(false);
    setError("");
    setActiveDocId(null);
    setInputKey((k) => k + 1);

    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  async function refresh() {
    if (!jobId) return;
    const mySeq = ++refreshSeqRef.current;
    setError("");

    try {
      const data = await listDocuments(jobId);
      if (refreshSeqRef.current !== mySeq) return; // stale
      setDocs(Array.isArray(data) ? (data as Doc[]) : []);
    } catch (e) {
      if (refreshSeqRef.current !== mySeq) return;
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Failed to load documents");
    }
  }

  const grouped = useMemo(() => {
    const by: Record<string, Doc[]> = {};
    for (const t of DOC_TYPES) by[t.key] = [];

    for (const d of docs) {
      const k = (d.doc_type ?? "").toLowerCase();
      if (!by[k]) by[k] = [];
      by[k].push(d);
    }

    for (const k of Object.keys(by)) {
      by[k].sort((a, b) => safeTime(b?.created_at) - safeTime(a?.created_at));
    }

    return by;
  }, [docs]);

  async function handleUpload(docType: string, file: File) {
    if (!jobId) return;
    if (!file) return;

    setError("");

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError("File must be 5 MB or smaller.");
      return;
    }

    setBusy(true);
    setActiveDocId(null); // no sentinel needed

    try {
      // 1) presign (creates DB row pending)
      const presign = await presignDocumentUpload(jobId, {
        doc_type: docType,
        filename: file.name,
        content_type: file.type || null,
        size_bytes: file.size || null,
      });

      const presign2 = presign as { document?: Doc; upload_url?: string };
      const doc = presign2?.document;
      const docId = doc?.id;
      const uploadUrl = presign2?.upload_url;

      if (!docId || !uploadUrl) {
        throw new Error("Presign failed (missing upload URL).");
      }

      // ✅ show progress on a REAL doc row immediately
      setActiveDocId(docId);

      // ✅ optimistic insert so the pending row appears right away
      setDocs((prev) => {
        const exists = prev.some((d) => d.id === docId);
        if (exists) return prev;
        return [
          {
            ...doc,
            doc_type: doc.doc_type ?? docType,
            original_filename: doc.original_filename ?? file.name,
            content_type: doc.content_type ?? file.type ?? null,
            status: doc.status ?? "pending",
            created_at: doc.created_at ?? new Date().toISOString(),
          },
          ...prev,
        ];
      });

      // 2) upload to S3
      await uploadToS3PresignedUrl(uploadUrl, file);

      // 3) confirm upload (server updates status + timestamps)
      await confirmDocumentUpload(jobId, {
        document_id: docId,
        size_bytes: file.size || null,
      });

      // 4) refresh docs from server truth
      await refresh();

      // 5) bump activity (fallback to now)
      onActivityChange?.(new Date().toISOString());

      // reset file input so same file can be selected again
      setInputKey((k) => k + 1);
    } catch (e) {
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Upload failed");
      // If presign created a pending doc row but upload failed, refresh so UI matches server state
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
      setActiveDocId(null);
    }
  }

  async function handleDownload(docId: number) {
    if (!jobId) return;
    setBusy(true);
    setActiveDocId(docId);
    setError("");

    try {
      const res = await presignDocumentDownload(jobId, docId);
      const url = (res as { download_url?: string } | null)?.download_url;
      if (!url) throw new Error("Download link missing.");
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Download failed");
    } finally {
      setBusy(false);
      setActiveDocId(null);
    }
  }

  async function handleDelete(docId: number) {
    if (!jobId) return;
    setBusy(true);
    setActiveDocId(docId);
    setError("");

    try {
      await deleteDocument(jobId, docId);

      // ✅ optimistic remove feels snappier
      setDocs((prev) => prev.filter((d) => d.id !== docId));

      await refresh();
      onActivityChange?.(new Date().toISOString());
    } catch (e) {
      const err = e as { message?: string } | null;
      setError(err?.message ?? "Delete failed");
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
      setActiveDocId(null);
    }
  }

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center justify-between gap-4">
        <div className="text-xl font-semibold">Documents</div>
        {busy && <div className="text-xs text-slate-400">Working…</div>}
      </div>

      {error && (
        <div className="mt-3 rounded-lg border border-red-900/60 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="mt-4 space-y-6">
        {DOC_TYPES.map((t) => (
          <DocumentSection
            key={t.key}
            type={t}
            items={grouped[t.key] ?? []}
            busy={busy}
            activeDocId={activeDocId}
            inputKey={inputKey}
            onUpload={handleUpload}
            onDownload={handleDownload}
            onDelete={handleDelete}
            DocRow={DocRow}
          />
        ))}
      </div>
    </div>
  );
}