import type { Dispatch, SetStateAction } from "react";
import type { Note } from "../../types/api";
import CollapseToggle from "../ui/CollapseToggle";

type NoteWithFields = Note & { body?: string; created_at?: string | null };

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

type Props = {
  notes: NoteWithFields[];
  noteText: string;
  setNoteText: Dispatch<SetStateAction<string>>;
  onAddNote: () => void | Promise<void>;
  onDeleteNote: (noteId: number) => void | Promise<void>;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
};

export default function NotesCard({
  notes,
  noteText,
  setNoteText,
  onAddNote,
  onDeleteNote,
  collapsed = false,
  onToggleCollapse,
}: Props) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="text-xl font-semibold">Notes</div>
        {onToggleCollapse && <CollapseToggle collapsed={collapsed} onToggle={onToggleCollapse} label="notes section" />}
      </div>

      {!collapsed && (
        <>
          <div className="space-y-3 mb-4">
            {(!notes || notes.length === 0) && (
              <div className="text-slate-400 text-sm">No notes yet.</div>
            )}

            {notes?.map((note) => (
              <div
                key={note.id}
                className="bg-slate-800/70 border border-slate-700 rounded-lg px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="text-xs text-slate-400 mb-1">{fmtDateTime(note.created_at)}</div>
                  <div className="text-slate-100 whitespace-pre-wrap break-words">
                    {note.body}
                  </div>
                </div>

                <button
                  onClick={() => onDeleteNote(note.id)}
                  title="Delete note"
                  className="shrink-0 text-red-400 hover:text-red-300 transition text-lg cursor-pointer"
                >
                  🗑️
                </button>
              </div>
            ))}
          </div>

          <div className="flex gap-3">
            <input
              className="flex-1 rounded-lg bg-slate-800/70 border border-slate-700 px-3 py-2 outline-none focus:ring-2 focus:ring-slate-500"
              placeholder="Add a note..."
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onAddNote();
              }}
            />

            <button
              onClick={onAddNote}
              className="rounded-lg px-5 py-2 text-sm font-semibold transition border border-slate-700 bg-slate-900/60 text-slate-200 hover:bg-slate-900 cursor-pointer"
            >
              Add
            </button>
          </div>
        </>
      )}
    </div>
  );
}