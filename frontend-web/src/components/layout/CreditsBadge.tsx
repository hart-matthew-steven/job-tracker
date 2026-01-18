import { NavLink } from "react-router-dom";

import { useCredits } from "../../hooks/useCredits";
import { ROUTES } from "../../routes/paths";
import { formatCurrencyFromCents } from "../../lib/formatCurrency";

type CreditsBadgeProps = {
  className?: string;
};

export default function CreditsBadge({ className }: CreditsBadgeProps) {
  const { balance, loading, error } = useCredits();
  const amount = balance ? formatCurrencyFromCents(balance.balance_cents, balance.currency) : "-";
  const statusLabel = !balance && loading ? "..." : amount;

  return (
    <NavLink
      to={ROUTES.billing}
      className={`inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-white hover:text-slate-900 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-white ${className ?? ""}`.trim()}
      title={error ?? undefined}
    >
      <span className="text-xs uppercase tracking-widest text-slate-400 dark:text-slate-500">Credits</span>
      <span aria-live="polite" aria-label="Available credits">
        {statusLabel}
      </span>
    </NavLink>
  );
}
