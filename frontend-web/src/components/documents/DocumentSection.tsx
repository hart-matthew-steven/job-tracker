// src/components/documents/DocumentSection.tsx
import type { ChangeEvent, ComponentType } from "react";

type DocType = { key: string; label: string; multiple: boolean };

type Doc = {
  id: number;
  created_at?: string | null;
  status?: string | null;
  doc_type?: string | null;
  original_filename?: string | null;
  content_type?: string | null;
};

type DocRowProps = {
  doc: Doc;
  busy?: boolean;
  activeDocId?: number | null;
  onDownload: () => void;
  onDelete: () => void;
};

type Props = {
  type: DocType;
  items: Doc[];
  busy: boolean;
  activeDocId: number | null;
  inputKey: number;
  onUpload: (docType: string, file: File) => Promise<void>;
  onDownload: (docId: number) => Promise<void> | void;
  onDelete: (docId: number) => Promise<void> | void;
  DocRow: ComponentType<DocRowProps> | null;
};

export default function DocumentSection({
  type,
  items,
  busy,
  activeDocId,
  inputKey,
  onUpload,
  onDownload,
  onDelete,
  DocRow,
}: Props) {
  const Row = DocRow;
  const singleDoc = !type.multiple ? items[0] : null;

  const hasSingleAlready = !type.multiple && !!singleDoc;
  const disableUpload = hasSingleAlready || busy;

  // ✅ If the currently-active doc belongs to this section, show “Uploading…”
  const isSectionActive = !!busy && !!activeDocId && (
    (!type.multiple && singleDoc?.id === activeDocId) ||
    (type.multiple && items.some((d) => d?.id === activeDocId))
  );

  // Keep it simple: common “documenty” types
  const accept =
    ".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    // allow selecting same file again next time
    e.target.value = "";

    if (disableUpload) return;
    if (files.length === 0) return;

    // Single: only first file
    if (!type.multiple) {
      await onUpload(type.key, files[0]);
      return;
    }

    // Multiple: upload sequentially (keeps UI predictable)
    for (const f of files) {
      // stop if parent marks busy mid-loop
      if (busy) break;
      await onUpload(type.key, f);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="font-semibold">{type.label}</div>

        <div className="flex items-center gap-2">
          {isSectionActive && (
            <span className="text-xs text-slate-400">Uploading…</span>
          )}

          <label
            className={[
              "inline-flex items-center gap-2 text-sm",
              disableUpload
                ? "cursor-not-allowed text-slate-500"
                : "cursor-pointer text-blue-300 hover:text-blue-200",
            ].join(" ")}
          >
            <input
              key={`${type.key}-${inputKey}`}
              type="file"
              className="hidden"
              disabled={disableUpload}
              accept={accept}
              multiple={!!type.multiple}
              onChange={handleFileChange}
            />
            <span
              className={[
                "rounded-md border px-3 py-1.5 transition",
                disableUpload
                  ? "border-slate-800 bg-slate-900/40 text-slate-500"
                  : "border-slate-700 bg-slate-800/70 hover:bg-slate-800",
              ].join(" ")}
              title={
                hasSingleAlready
                  ? "Delete the existing document to upload a new one"
                  : type.multiple
                    ? "Upload one or more files"
                    : "Upload"
              }
            >
              Upload
            </span>
          </label>
        </div>
      </div>

      {hasSingleAlready && (
        <div className="text-xs text-slate-500">
          Delete the existing file to upload a new one.
        </div>
      )}

      {/* Single */}
      {!type.multiple && (
        <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3">
          {!singleDoc ? (
            <div className="text-sm text-slate-400">No document uploaded.</div>
          ) : (
            Row && (
              <Row
                doc={singleDoc}
                busy={busy}
                activeDocId={activeDocId}
                onDownload={() => onDownload(singleDoc.id)}
                onDelete={() => onDelete(singleDoc.id)}
              />
            )
          )}
        </div>
      )}

      {/* Multiple */}
      {type.multiple && (
        <div className="space-y-2">
          {items.length === 0 && (
            <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3 text-sm text-slate-400">
              No documents uploaded.
            </div>
          )}

          {items.map((doc) => (
            <div
              key={doc.id}
              className="rounded-lg border border-slate-800 bg-slate-950/30 p-3"
            >
              {Row && (
                <Row
                  doc={doc}
                  busy={busy}
                  activeDocId={activeDocId}
                  onDownload={() => onDownload(doc.id)}
                  onDelete={() => onDelete(doc.id)}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}