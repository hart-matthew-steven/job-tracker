export type PackDisplayConfig = {
  label: string;
  badge?: string;
  description?: string;
};

const DEFAULT_PACKS: Record<string, PackDisplayConfig> = {
  starter: {
    label: "Starter",
    description: "Great for kicking off AI experiments and resume touch-ups.",
  },
  pro: {
    label: "Plus",
    badge: "Most popular",
    description: "Enough credits for frequent resume edits and cover letter drafts.",
  },
  expert: {
    label: "Max",
    badge: "Best value",
    description: "High-volume plan for power users running AI on every application.",
  },
};

function parsePackConfig(): Record<string, PackDisplayConfig> {
  const raw = (import.meta.env.VITE_BILLING_PACK_CONFIG ?? "").trim();
  if (!raw) return DEFAULT_PACKS;
  try {
    const parsed = JSON.parse(raw) as Record<string, Partial<PackDisplayConfig>>;
    const entries = Object.entries(DEFAULT_PACKS).map(([key, fallback]) => {
      const override = parsed?.[key];
      if (!override || typeof override !== "object") return [key, fallback] as const;
      return [key, { ...fallback, ...override }] as const;
    });
    return Object.fromEntries(entries);
  } catch {
    return DEFAULT_PACKS;
  }
}

export const BILLING_PACK_CONFIG = parsePackConfig();
export const ORDERED_PACK_KEYS = Object.keys(BILLING_PACK_CONFIG);

export function getPackDisplay(key: string): PackDisplayConfig {
  return BILLING_PACK_CONFIG[key] ?? { label: key };
}
