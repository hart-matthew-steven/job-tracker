import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import VerifyEmailPage from "./VerifyEmailPage";
import { renderWithRouter } from "../../test/testUtils";

const router = vi.hoisted(() => ({
  nav: vi.fn(),
}));

const cognitoApi = vi.hoisted(() => ({
  sendEmailVerificationCode: vi.fn(),
  confirmEmailVerificationCode: vi.fn(),
}));

const tokenManager = vi.hoisted(() => ({
  getSession: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);
vi.mock("../../auth/tokenManager", () => tokenManager);

vi.mock("react-router-dom", async () => {
  const mod = await import("react-router-dom");
  return {
    ...mod,
    useNavigate: () => router.nav,
  };
});

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    cognitoApi.sendEmailVerificationCode.mockResolvedValue({ message: "Sent" });
    cognitoApi.confirmEmailVerificationCode.mockResolvedValue({ message: "Email verified." });
    tokenManager.getSession.mockReturnValue(null);
  });

  it("submits code and redirects to login when no session", async () => {
    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com&next=%2Fjobs",
      path: "/verify",
    });

    await screen.findByPlaceholderText("you@example.com");
    await waitFor(() => expect(cognitoApi.sendEmailVerificationCode).toHaveBeenCalledWith({ email: "a@b.com" }));
    const emailInput = screen.getByPlaceholderText("you@example.com");
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, "a@b.com");
    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm account" }));

    await waitFor(() =>
      expect(cognitoApi.confirmEmailVerificationCode).toHaveBeenCalledWith({ email: "a@b.com", code: "123456" })
    );
    expect(router.nav).toHaveBeenCalledWith("/login?next=%2Fjobs", { replace: true });
  });

  it("redirects to app when session exists", async () => {
    tokenManager.getSession.mockReturnValue({ accessToken: "token123" });
    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com&next=%2Fjobs",
      path: "/verify",
    });

    await waitFor(() => expect(cognitoApi.sendEmailVerificationCode).toHaveBeenCalledWith({ email: "a@b.com" }));
    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Confirm account" }));

    await waitFor(() =>
      expect(cognitoApi.confirmEmailVerificationCode).toHaveBeenCalledWith({ email: "a@b.com", code: "123456" })
    );
    expect(router.nav).toHaveBeenCalledWith("/jobs", { replace: true });
  });

  it("skips initial resend when sent flag provided", async () => {
    vi.useRealTimers();
    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com&sent=1",
      path: "/verify",
    });

    await screen.findByText(/We just sent a verification code/i);
    expect(cognitoApi.sendEmailVerificationCode).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /Resend available/i })).toBeDisabled();
  });

  it("uses cooldown returned by backend when sending manually", async () => {
    cognitoApi.sendEmailVerificationCode.mockResolvedValue({
      message: "Sent",
      resend_available_in_seconds: 1,
    });

    renderWithRouter(<VerifyEmailPage />, {
      route: "/verify?email=a%40b.com",
      path: "/verify",
    });

    await waitFor(() => expect(cognitoApi.sendEmailVerificationCode).toHaveBeenCalledWith({ email: "a@b.com" }));
    expect(screen.getByRole("button", { name: /Resend available/i })).toBeDisabled();
    await new Promise((resolve) => setTimeout(resolve, 1100));
    await waitFor(() => expect(screen.getByRole("button", { name: /Resend code/i })).toBeEnabled());
  });

  it("shows error when API rejects", async () => {
    vi.useRealTimers();
    cognitoApi.confirmEmailVerificationCode.mockRejectedValueOnce(new Error("Code expired"));

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
