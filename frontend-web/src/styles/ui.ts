// Shared Tailwind class strings to reduce duplication.
// Keep these minimal and purely presentational (Phase 4 refactor).

export const input =
  "rounded-lg border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-600/30 " +
  "border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 " +
  "dark:border-slate-700 dark:bg-slate-950/30 dark:text-slate-100 dark:placeholder:text-slate-400";

export const buttonBase = "rounded-lg font-semibold transition border";

export const buttonNeutral =
  `${buttonBase} border-slate-300 bg-white text-slate-700 hover:bg-slate-100 ` +
  "dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200 dark:hover:bg-slate-900";

export const buttonPrimary =
  `${buttonBase} border-slate-300 bg-slate-900 text-white hover:bg-slate-800 ` +
  "dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-100 dark:hover:bg-slate-800";

export const buttonDanger =
  `${buttonBase} border-red-800/70 bg-red-50 text-red-900 hover:bg-red-100 ` +
  "dark:border-red-800/70 dark:bg-red-950/20 dark:text-red-200 dark:hover:bg-red-950/30";

export const buttonDisabled =
  "cursor-not-allowed border-slate-300 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-500";

export const panel =
  "rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900/30";

export const chip =
  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold";


