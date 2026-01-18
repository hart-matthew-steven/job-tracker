import { useEffect, useMemo } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { useCredits } from "../../hooks/useCredits";
import { ROUTES } from "../../routes/paths";
import { formatCurrencyFromCents } from "../../lib/formatCurrency";

function resolveStatus(pathname: string, searchParams: URLSearchParams): "success" | "canceled" | "unknown" {
  const path = pathname.toLowerCase();
  const statusParam = (searchParams.get("status") || "").toLowerCase();
  const successFlag = (searchParams.get("success") || "").toLowerCase();
  const canceledFlag = (searchParams.get("canceled") || searchParams.get("cancelled") || "").toLowerCase();

  if (statusParam === "success" || successFlag === "true" || path.endsWith("/success")) return "success";
  if (statusParam === "canceled" || statusParam === "cancelled" || canceledFlag === "true" || path.endsWith("/cancelled")) {
    return "canceled";
  }
  return "unknown";
}

export default function BillingReturnPage() {
  const credits = useCredits();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const status = useMemo(() => resolveStatus(location.pathname, searchParams), [location.pathname, searchParams]);

  const { refresh } = credits;

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const { title, body } = useMemo(() => {
    switch (status) {
      case "success":
        return {
          title: "Payment successful",
          body: "Thanks for purchasing credits. We've refreshed your balance below.",
        };
      case "canceled":
        return {
          title: "Checkout canceled",
          body: "No charges were made. You can restart the checkout whenever you're ready.",
        };
      default:
        return {
          title: "Checkout status",
          body: "We couldn't confirm the checkout status. If you completed a purchase, your credits will appear below once the webhook runs.",
        };
    }
  }, [status]);

  const balanceLabel = credits.balance
    ? formatCurrencyFromCents(credits.balance.balance_cents, credits.balance.currency)
    : credits.loading
      ? "..."
      : "-";

  return (
    <section className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="rounded-3xl border border-slate-200 bg-white/70 p-6 text-slate-900 shadow-sm dark:border-slate-800 dark:bg-slate-900/40 dark:text-white">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">Stripe</p>
        <h1 className="mt-2 text-3xl font-semibold">{title}</h1>
        <p className="mt-2 text-slate-600 dark:text-slate-300">{body}</p>
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 p-4 dark:border-slate-800 dark:bg-slate-950/40">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Current balance</p>
          <p className="mt-1 text-2xl font-semibold" aria-live="polite">
            {balanceLabel}
          </p>
          {credits.error && !credits.loading && (
            <p className="mt-2 text-sm text-amber-600">Unable to refresh credits yet. Please reload this page in a few seconds.</p>
          )}
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            to={ROUTES.billing}
            className="inline-flex items-center justify-center rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white dark:focus-visible:ring-white dark:focus-visible:ring-offset-slate-900"
          >
            Back to billing
          </Link>
          <button
            type="button"
            onClick={() => void credits.refresh()}
            className="text-sm font-medium text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-300 dark:hover:text-white"
          >
            Refresh balance
          </button>
        </div>
      </div>
    </section>
  );
}
