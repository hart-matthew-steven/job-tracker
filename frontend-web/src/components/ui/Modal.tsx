import { useEffect } from "react";

type Props = {
  open: boolean;
  title?: string;
  children: React.ReactNode;
  onClose: () => void;
  maxWidthClassName?: string;
};

export default function Modal({ open, title, children, onClose, maxWidthClassName = "max-w-xl" }: Props) {
  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />

      <div className="absolute inset-0 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto w-full">
          <div
            className={[
              "mx-auto w-full",
              maxWidthClassName,
              "rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-950",
            ].join(" ")}
            role="dialog"
            aria-modal="true"
            aria-label={title || "Dialog"}
          >
            <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title ?? ""}</div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-slate-200 bg-white px-2.5 py-2 text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200 dark:hover:bg-slate-900"
                aria-label="Close"
              >
                <span aria-hidden="true">✕</span>
              </button>
            </div>

            <div className="px-5 py-5">{children}</div>
          </div>
        </div>
      </div>
    </div>
  );
}


