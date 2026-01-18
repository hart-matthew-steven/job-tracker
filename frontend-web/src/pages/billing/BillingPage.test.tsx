import { describe, expect, it, vi, beforeEach, beforeAll, afterAll } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";

import BillingPage from "./BillingPage";
import { CreditsProvider } from "../../context/CreditsContext";
import { renderWithRouter } from "../../test/testUtils";

const api = vi.hoisted(() => ({
  getCreditsBalance: vi.fn(),
  listCreditPacks: vi.fn(),
  createStripeCheckoutSession: vi.fn(),
}));

vi.mock("../../api", () => ({
  getCreditsBalance: api.getCreditsBalance,
  listCreditPacks: api.listCreditPacks,
  createStripeCheckoutSession: api.createStripeCheckoutSession,
}));

const originalLocation = window.location;
const assignSpy = vi.fn();

beforeAll(() => {
  const url = new URL(originalLocation.href);
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      ...url,
      assign: assignSpy,
    } as unknown as Location,
  });
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("BillingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    assignSpy.mockReset();
    api.getCreditsBalance.mockResolvedValue({
      currency: "usd",
      balance_cents: 5000,
      balance_dollars: "50.00",
      lifetime_granted_cents: 5000,
      lifetime_spent_cents: 0,
      as_of: new Date().toISOString(),
    });
    api.listCreditPacks.mockResolvedValue([
      { key: "starter", price_id: "price_starter", credits: 500, currency: "usd", display_price_dollars: "5.00" },
      { key: "pro", price_id: "price_pro", credits: 1500, currency: "usd", display_price_dollars: "12.00" },
      { key: "expert", price_id: "price_expert", credits: 4000, currency: "usd", display_price_dollars: "29.00" },
    ]);
    api.createStripeCheckoutSession.mockResolvedValue({
      checkout_session_id: "cs_123",
      checkout_url: "https://checkout.test/session/cs_123",
      currency: "usd",
      pack_key: "starter",
      credits_granted: 500,
    });
  });

  it("renders packs and starts checkout on Buy", async () => {
    const user = userEvent.setup();
    renderWithRouter(
      <CreditsProvider>
        <BillingPage />
      </CreditsProvider>,
      { route: "/billing", path: "/billing" }
    );

    expect(await screen.findByText("Starter")).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Buy" })[0]);
    expect(api.createStripeCheckoutSession).toHaveBeenCalledWith("starter");
    expect(assignSpy).toHaveBeenCalledWith("https://checkout.test/session/cs_123");
  });
});
