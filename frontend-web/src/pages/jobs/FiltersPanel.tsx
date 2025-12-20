import type { JobsViewId, StatusFilterId } from "./constants";
import { JOBS_VIEW_OPTIONS, STATUS_FILTER_OPTIONS } from "./constants";
import { buttonNeutral, chip, input } from "../../styles/ui";

type Props = {
  // Tag filter
  selectedTags: string[];
  onRemoveTag: (tag: string) => void;
  tagQuery: string;
  onTagQueryChange: (next: string) => void;
  tagSuggestions: string[];
  tagFilterOpen: boolean;
  onTagFilterOpenChange: (open: boolean) => void;
  onSelectTagSuggestion: (tag: string) => void;
  onClearTagFilter: () => void;

  // View chips
  view: JobsViewId;
  viewCounts: Record<JobsViewId, number>;
  onSelectView: (view: JobsViewId) => void;

  // Status chips
  selectedStatuses: StatusFilterId[];
  statusCounts: Record<StatusFilterId, number>;
  onToggleStatus: (status: StatusFilterId) => void;
};

export default function FiltersPanel({
  selectedTags,
  onRemoveTag,
  tagQuery,
  onTagQueryChange,
  tagSuggestions,
  tagFilterOpen,
  onTagFilterOpenChange,
  onSelectTagSuggestion,
  onClearTagFilter,
  view,
  viewCounts,
  onSelectView,
  selectedStatuses,
  statusCounts,
  onToggleStatus,
}: Props) {
  return (
    <>
      <div className="mb-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Tag filter</label>
        {selectedTags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {selectedTags.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onRemoveTag(t)}
                className={`${chip} border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-200 dark:hover:bg-slate-900/60`}
                title="Remove tag filter"
              >
                {t} <span className="text-slate-400">✕</span>
              </button>
            ))}
          </div>
        )}

        <div className="mt-2 flex items-center gap-2">
          <div className="relative flex-1">
            <input
              value={tagQuery}
              onChange={(e) => {
                onTagQueryChange(e.target.value);
                onTagFilterOpenChange(true);
              }}
              onFocus={() => onTagFilterOpenChange(true)}
              onKeyDown={(e) => {
                if (e.key === "Escape") onTagFilterOpenChange(false);
                if (e.key === "Enter") {
                  const first = tagSuggestions[0];
                  if (first && String(tagQuery ?? "").trim()) onSelectTagSuggestion(first);
                }
              }}
              className={`w-full ${input}`}
              placeholder="Search tags… (Enter to add)"
            />

            {tagFilterOpen && tagSuggestions.length > 0 && (
              <div className="absolute z-20 mt-2 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-800 dark:bg-slate-950">
                <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-600 border-b border-slate-200 dark:text-slate-500 dark:border-slate-800">
                  {String(tagQuery ?? "").trim() ? "Matching tags" : "Popular tags"}
                </div>
                <div className="max-h-56 overflow-auto">
                  {tagSuggestions.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onMouseDown={(ev) => {
                        // prevent input blur before click
                        ev.preventDefault();
                      }}
                      onClick={() => onSelectTagSuggestion(t)}
                      className="w-full text-left px-3 py-2 text-sm text-slate-800 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900/60"
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          {(!!tagQuery.trim() || selectedTags.length > 0) && (
            <button
              type="button"
              onClick={onClearTagFilter}
              className={`px-3 py-2 text-xs ${buttonNeutral}`}
              title="Clear tag filter"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-2">
        {(JOBS_VIEW_OPTIONS.map((o) => o.value) as JobsViewId[]).map((v) => {
          const isActive = view === v;
          const count = viewCounts[v] ?? 0;
          return (
            <button
              key={v}
              type="button"
              onClick={() => onSelectView(v)}
              className={[
                "rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                isActive
                  ? "border-slate-300 bg-slate-200 text-slate-900 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-300 dark:hover:bg-slate-900/60",
              ].join(" ")}
              title="Filter jobs by view"
            >
              {JOBS_VIEW_OPTIONS.find((o) => o.value === v)?.label ?? v}{" "}
              <span className={isActive ? "text-slate-600 dark:text-slate-200" : "text-slate-500"}>({count})</span>
            </button>
          );
        })}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTER_OPTIONS.map((o) => {
          const isSelected = selectedStatuses.includes(o.value);
          const count = statusCounts[o.value] ?? 0;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onToggleStatus(o.value)}
              className={[
                "rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                isSelected
                  ? "border-slate-300 bg-slate-200 text-slate-900 dark:border-slate-600 dark:bg-slate-800/70 dark:text-slate-100"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950/30 dark:text-slate-300 dark:hover:bg-slate-900/60",
              ].join(" ")}
              title="Filter jobs by status (multi-select)"
            >
              {o.label}{" "}
              <span className={isSelected ? "text-slate-600 dark:text-slate-200" : "text-slate-500"}>({count})</span>
            </button>
          );
        })}
      </div>
    </>
  );
}


