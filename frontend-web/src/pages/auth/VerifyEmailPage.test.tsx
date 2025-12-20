import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";

import VerifyEmailPage from "./VerifyEmailPage";
import { renderWithRouter } from "../../test/testUtils";

const router = vi.hoisted(() => ({
  nav: vi.fn(),
}));

const api = vi.hoisted(() => ({
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../../api", () => api);

vi.mock("react-router-dom", async () => {
  const mod = await import("react-router-dom");
  return {
    ...mod,
    useNavigate: () => router.nav,
  };
});

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows error toast when token is missing", async () => {
    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com&next=%2Fjobs",
      path: "/verify",
    });

    expect(
      (await screen.findAllByText("Missing verification token. Please use the link from your email.")).length
    ).toBeGreaterThan(0);
    expect(api.verifyEmail).not.toHaveBeenCalled();
  });

  it("verifies, shows success toast, then redirects to login", async () => {
    vi.useFakeTimers();
    api.verifyEmail.mockResolvedValueOnce({ message: "Email verified. You can now log in." });

    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?token=tok123&next=%2Fjobs",
      path: "/verify",
    });

    // Let the verifyEmail promise resolve and the redirect timeout be scheduled.
    await Promise.resolve();
    await Promise.resolve();

    await vi.advanceTimersByTimeAsync(950);

    expect(api.verifyEmail).toHaveBeenCalledWith("tok123");
    expect(router.nav).toHaveBeenCalledWith("/login?next=%2Fjobs", { replace: true });
  });
});


