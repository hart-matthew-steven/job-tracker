import { createContext, useContext } from "react";

export type ToastVariant = "success" | "error" | "info";

export type Toast = {
  id: string;
  message: string;
  title?: string;
  variant: ToastVariant;
};

export type ToastInput = Omit<Toast, "id"> & { durationMs?: number };

export type ToastContextValue = {
  push: (t: ToastInput) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
};

export const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider />");
  return ctx;
}


