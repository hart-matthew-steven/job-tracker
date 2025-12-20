import Modal from "../../components/ui/Modal";
import type { SavedView } from "../../types/api";
import { buttonDanger, buttonDisabled, buttonNeutral, buttonPrimary, input, panel } from "../../styles/ui";

type Props = {
  open: boolean;
  onClose: () => void;

  viewsBusy: boolean;
  saveName: string;
  onSaveNameChange: (next: string) => void;
  onSave: () => void;

  savedViews: SavedView[];
  selectedSavedViewId: number | null;
  onApply: (sv: SavedView) => void;
  onDelete: (sv: SavedView) => void;
};

export default function SavedViewsModal({
  open,
  onClose,
  viewsBusy,
  saveName,
  onSaveNameChange,
  onSave,
  savedViews,
  selectedSavedViewId,
  onApply,
  onDelete,
}: Props) {
  return (
    <Modal open={open} onClose={onClose} title="Saved views" maxWidthClassName="max-w-2xl">
      <div className="space-y-4">
        <div className={`${panel} p-4`}>
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Save current view</div>
          <div className="mt-1 text-xs text-slate-600 dark:text-slate-400">
            Saves your current search, tag filter, pipeline chip selection, and sort.
          </div>

          <div className="mt-3 flex flex-col sm:flex-row gap-2">
            <input
              value={saveName}
              onChange={(e) => onSaveNameChange(e.target.value)}
              className={`flex-1 ${input}`}
              placeholder="View name (e.g. Remote + follow-up)"
              disabled={viewsBusy}
            />
            <button
              type="button"
              disabled={viewsBusy}
              onClick={onSave}
              className={[
                "px-3 py-2 text-xs",
                viewsBusy ? buttonDisabled : buttonPrimary,
              ].join(" ")}
            >
              Save
            </button>
          </div>
        </div>

        <div className={`${panel} p-4`}>
          <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Your saved views</div>
          <div className="mt-3 space-y-2">
            {savedViews.length === 0 ? (
              <div className="text-sm text-slate-600 dark:text-slate-400">No saved views yet.</div>
            ) : (
              savedViews.map((sv) => {
                const isSelected = selectedSavedViewId === sv.id;
                return (
                  <div
                    key={sv.id}
                    className={[
                      "flex items-center justify-between gap-3 rounded-lg border px-3 py-2",
                      isSelected
                        ? "border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-950/40"
                        : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950/20",
                    ].join(" ")}
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">{sv.name}</div>
                      <div className="text-xs text-slate-500 truncate">
                        Updated {new Date(sv.updated_at || sv.created_at).toLocaleString()}
                      </div>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <button
                        type="button"
                        disabled={viewsBusy}
                        onClick={() => onApply(sv)}
                        className={["px-3 py-2 text-xs", viewsBusy ? buttonDisabled : buttonNeutral].join(" ")}
                      >
                        Apply
                      </button>
                      <button
                        type="button"
                        disabled={viewsBusy}
                        onClick={() => onDelete(sv)}
                        className={["px-3 py-2 text-xs", viewsBusy ? buttonDisabled : buttonDanger].join(" ")}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}


