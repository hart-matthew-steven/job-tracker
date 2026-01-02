import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import VerifyEmailPage from "./VerifyEmailPage";
import { renderWithRouter } from "../../test/testUtils";

const router = vi.hoisted(() => ({
  nav: vi.fn(),
}));

const cognitoApi = vi.hoisted(() => ({
  cognitoConfirm: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);

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
    vi.useRealTimers();
  });

  it("submits code and redirects to login", async () => {
    cognitoApi.cognitoConfirm.mockResolvedValueOnce({ message: "Account verified." });

    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com&next=%2Fjobs",
      path: "/verify",
    });

    await screen.findByPlaceholderText("you@example.com");
    const emailInput = screen.getByPlaceholderText("you@example.com");
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, "a@b.com");
    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm account" }));

    await waitFor(() => expect(cognitoApi.cognitoConfirm).toHaveBeenCalledWith({ email: "a@b.com", code: "123456" }));
    expect(router.nav).toHaveBeenCalledWith("/login?next=%2Fjobs", { replace: true });
  });

  it("shows error when API rejects", async () => {
    cognitoApi.cognitoConfirm.mockRejectedValueOnce(new Error("Code expired"));

    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify",
      path: "/verify",
    });

    const emailInput = screen.getByPlaceholderText("you@example.com");
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, "a@b.com");
    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm account" }));

    expect((await screen.findAllByText(/Code expired/)).length).toBeGreaterThan(0);
  });
});
