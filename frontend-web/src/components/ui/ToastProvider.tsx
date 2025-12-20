import { useCallback, useMemo, useRef, useState } from "react";
import type { Toast, ToastContextValue, ToastInput, ToastVariant } from "./toast";
import { ToastContext } from "./toast";

function colorFor(v: ToastVariant): string {
  if (v === "success") return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-100";
  if (v === "error") return "border-red-300 bg-red-50 text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-100";
  return "border-slate-200 bg-white text-slate-900 dark:border-slate-800 dark:bg-slate-950/70 dark:text-slate-100";
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (input: ToastInput) => {
      const id = `t_${Date.now()}_${++seq.current}`;
      const toast: Toast = {
        id,
        variant: input.variant,
        title: input.title,
        message: input.message,
      };

      setToasts((prev) => [toast, ...prev].slice(0, 4));

      const duration = Math.max(1200, input.durationMs ?? 4000);
      window.setTimeout(() => remove(id), duration);
    },
    [remove]
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      push,
      success: (message, title) => push({ variant: "success", message, title }),
      error: (message, title) => push({ variant: "error", message, title }),
      info: (message, title) => push({ variant: "info", message, title }),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}

      <div className="fixed right-4 top-4 z-[60] w-[min(420px,calc(100vw-2rem))] space-y-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={[
              "rounded-xl border px-4 py-3 shadow-lg backdrop-blur",
              colorFor(t.variant),
            ].join(" ")}
            role="status"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                {t.title && <div className="text-sm font-semibold">{t.title}</div>}
                <div className="text-sm text-slate-700 dark:text-slate-100/90 break-words">{t.message}</div>
              </div>

              <button
                type="button"
                className="shrink-0 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950/50 dark:text-slate-200 dark:hover:bg-slate-900"
                onClick={() => remove(t.id)}
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}