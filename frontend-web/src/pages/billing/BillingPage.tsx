import { useCallback, useEffect, useMemo, useState } from "react";

import { listCreditPacks, createStripeCheckoutSession } from "../../api";
import type { CreditPack } from "../../types/api";
import { useCredits } from "../../hooks/useCredits";
import { useToast } from "../../components/ui/toast";
import { formatCurrencyFromCents } from "../../lib/formatCurrency";
import { getPackDisplay, ORDERED_PACK_KEYS } from "../../config/billing";

export default function BillingPage() {
  const toast = useToast();
  const credits = useCredits();
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [packsLoading, setPacksLoading] = useState(true);
  const [packsError, setPacksError] = useState<string | null>(null);
  const [pendingPack, setPendingPack] = useState<string | null>(null);

  const packMap = useMemo(() => new Map(packs.map((pack) => [pack.key, pack])), [packs]);

  const packKeys = useMemo(() => {
    const keys = new Set<string>(ORDERED_PACK_KEYS);
    packs.forEach((pack) => keys.add(pack.key));
    return Array.from(keys);
  }, [packs]);

  const loadPacks = useCallback(async () => {
    setPacksLoading(true);
    setPacksError(null);
    try {
      const response = await listCreditPacks();
      setPacks(response);
    } catch (err) {
      setPacksError((err as Error)?.message || "Unable to load credit packs.");
    } finally {
      setPacksLoading(false);
    }
  }, []);

  const refreshCredits = credits.refresh;

  useEffect(() => {
    loadPacks();
    void refreshCredits();
  }, [loadPacks, refreshCredits]);

  const handleCheckout = useCallback(
    async (rawKey: string) => {
      const normalized = rawKey.trim().toLowerCase();
      if (!normalized) return;
      setPendingPack(normalized);
      try {
        const session = await createStripeCheckoutSession(normalized);
        window.location.assign(session.checkout_url);
      } catch (err) {
        const message = (err as Error)?.message || "Unable to start checkout.";
        toast.error(message, "Billing");
      } finally {
        setPendingPack(null);
      }
    },
    [toast]
  );

  const balanceLabel = credits.balance
    ? formatCurrencyFromCents(credits.balance.balance_cents, credits.balance.currency)
    : credits.loading
      ? "..."
      : "-";

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-8">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">Billing</p>
        <h1 className="text-3xl font-semibold text-slate-900 dark:text-white">Buy credits</h1>
        <p className="max-w-3xl text-base text-slate-600 dark:text-slate-300">
          Credits are prepaid and consumed by AI chat/conversation calls. Checkout happens on Stripe; once payment
          succeeds, the webhook mints credits and this page refreshes your balance automatically.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl border border-slate-200 bg-white/70 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/40">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Available credits</p>
          <p className="mt-2 text-4xl font-semibold text-slate-900 dark:text-white" aria-live="polite">
            {balanceLabel}
          </p>
          {credits.error && !credits.loading && (
            <p className="mt-2 text-sm text-amber-600">Unable to refresh credits right now. Try again in a moment.</p>
          )}
          <button
            type="button"
            onClick={() => void refreshCredits()}
            className="mt-4 text-sm font-medium text-slate-500 underline-offset-4 hover:underline"
          >
            Refresh balance
          </button>
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white/70 p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/40">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">How credits work</p>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600 dark:text-slate-300">
            <li>Each credit equals one cent of OpenAI usage.</li>
            <li>Requests reserve credits up front and refund any unused amount.</li>
            <li>Billing is pay-as-you-go - no subscriptions, and unused credits roll over.</li>
          </ul>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Choose a pack</h2>
          {packsLoading && <span className="text-sm text-slate-500">Loading packs...</span>}
        </div>
        {packsError && (
          <div className="rounded-2xl border border-amber-400 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/50 dark:bg-amber-500/10 dark:text-amber-200">
            <div className="flex items-center justify-between">
              <p>{packsError}</p>
              <button type="button" className="font-semibold underline" onClick={() => loadPacks()}>
                Retry
              </button>
            </div>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-3">
          {packKeys.map((key) => {
            const display = getPackDisplay(key);
            const pack = packMap.get(key);
            const priceLabel =
              pack && !Number.isNaN(Number(pack.display_price_dollars))
                ? formatCurrencyFromCents(Math.round(Number(pack.display_price_dollars) * 100), pack.currency)
                : "-";
            const creditsLabel = pack ? `${pack.credits.toLocaleString()} credits` : "Unavailable";
            const disabled = !pack;
            const isPending = pendingPack === key;

            return (
              <div key={key} className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white/80 p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900/40">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{display.label}</h3>
                  {display.badge && (
                      <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white dark:bg-slate-100 dark:text-slate-900">
                        {display.badge}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{display.description}</p>
                </div>
                <div>
                  <p className="text-3xl font-semibold text-slate-900 dark:text-white">{priceLabel}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{creditsLabel}</p>
                </div>
                <button
                  type="button"
                  disabled={disabled || isPending}
                  onClick={() => handleCheckout(key)}
                  className="rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white disabled:dark:bg-slate-700 disabled:dark:text-slate-400"
                >
                  {isPending ? "Redirecting..." : "Buy"}
                </button>
              </div>
            );
          })}
        </div>
      </div>

    </section>
  );
}
