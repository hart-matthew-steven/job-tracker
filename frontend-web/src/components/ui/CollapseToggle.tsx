type Props = {
  collapsed: boolean;
  onToggle: () => void;
  label?: string;
};

export default function CollapseToggle({ collapsed, onToggle, label = "section" }: Props) {
  const verb = collapsed ? "Expand" : "Collapse";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={`${verb} ${label.toLowerCase()}`}
      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700/70 bg-slate-900/40 text-slate-200 transition hover:bg-slate-900/60"
    >
      <svg
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={`h-4 w-4 transition-transform duration-200 ${collapsed ? "rotate-0" : "-rotate-180"}`}
        aria-hidden="true"
      >
        <path
          d="M5 8l5 5 5-5"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

