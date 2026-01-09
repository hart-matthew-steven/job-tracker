import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import CreditsBadge from "./CreditsBadge";
import { CreditsProvider } from "../../context/CreditsContext";

const api = vi.hoisted(() => ({
  getCreditsBalance: vi.fn(),
}));

vi.mock("../../api", () => ({
  getCreditsBalance: api.getCreditsBalance,
}));

describe("CreditsBadge", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches balance and renders amount", async () => {
    api.getCreditsBalance.mockResolvedValue({
      currency: "usd",
      balance_cents: 2500,
      balance_dollars: "25.00",
      lifetime_granted_cents: 2500,
      lifetime_spent_cents: 0,
      as_of: new Date().toISOString(),
    });

    render(
      <MemoryRouter>
        <CreditsProvider>
          <CreditsBadge />
        </CreditsProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText("$25.00")).toBeInTheDocument();
    expect(api.getCreditsBalance).toHaveBeenCalledTimes(1);
  });
});
