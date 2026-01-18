import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";

import BillingReturnPage from "./BillingReturnPage";
import { CreditsProvider } from "../../context/CreditsContext";
import { renderWithRouter } from "../../test/testUtils";

const api = vi.hoisted(() => ({
  getCreditsBalance: vi.fn(),
}));

vi.mock("../../api", () => ({
  getCreditsBalance: api.getCreditsBalance,
}));

describe("BillingReturnPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getCreditsBalance.mockResolvedValue({
      currency: "usd",
      balance_cents: 8000,
      balance_dollars: "80.00",
      lifetime_granted_cents: 8000,
      lifetime_spent_cents: 0,
      as_of: new Date().toISOString(),
    });
  });

  it("shows success state and refreshes balance", async () => {
    renderWithRouter(
      <CreditsProvider>
        <BillingReturnPage />
      </CreditsProvider>,
      { route: "/billing/return?status=success", path: "/billing/return" }
    );

    expect(await screen.findByText("Payment successful")).toBeInTheDocument();
    await screen.findByText("$80.00");
    expect(api.getCreditsBalance.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("handles canceled legacy path", async () => {
    renderWithRouter(
      <CreditsProvider>
        <BillingReturnPage />
      </CreditsProvider>,
      { route: "/billing/stripe/cancelled", path: "/billing/stripe/cancelled" }
    );

    expect(await screen.findByText("Checkout canceled")).toBeInTheDocument();
  });
});
