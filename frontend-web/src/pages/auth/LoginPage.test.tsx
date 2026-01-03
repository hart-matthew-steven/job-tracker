import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "./LoginPage";
import { renderWithRouter } from "../../test/testUtils";

const cognitoApi = vi.hoisted(() => ({
  cognitoLogin: vi.fn(),
  sendEmailVerificationCode: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);

const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
}));

vi.mock("../../api", () => api);

const auth = vi.hoisted(() => ({
  setSession: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => auth,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getCurrentUser.mockResolvedValue({ email: "me@example.com", is_email_verified: true });
    cognitoApi.sendEmailVerificationCode.mockResolvedValue({ message: "Verification code sent." });
  });

  it("logs in and navigates to next when already verified", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoLogin.mockResolvedValueOnce({
      status: "OK",
      tokens: { access_token: "t_access", expires_in: 3600, token_type: "Bearer" },
    });

    renderWithRouter(<LoginPage />, {
      route: "/login?next=%2Fjobs",
      path: "/login",
      extraRoutes: [{ path: "/jobs", element: <div>JobsRoute</div> }],
    });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(auth.setSession).toHaveBeenCalledWith({
      access_token: "t_access",
      expires_in: 3600,
      token_type: "Bearer",
    });
    expect(await screen.findByText("JobsRoute")).toBeInTheDocument();
  });

  it("sends verification email and routes to verify screen when not verified", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoLogin.mockResolvedValueOnce({
      status: "OK",
      tokens: { access_token: "t_access", expires_in: 3600, token_type: "Bearer" },
    });
    api.getCurrentUser.mockResolvedValueOnce({ email: "me@example.com", is_email_verified: false });

    renderWithRouter(<LoginPage />, {
      route: "/login?next=%2Fjobs",
      path: "/login",
      extraRoutes: [{ path: "/verify", element: <div>VerifyPage</div> }],
    });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await screen.findByText("VerifyPage");
    expect(cognitoApi.sendEmailVerificationCode).toHaveBeenCalledWith({ email: "me@example.com" });
  });

  it("routes to MFA setup when Cognito asks for TOTP enrollment", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoLogin.mockResolvedValueOnce({
      status: "CHALLENGE",
      next_step: "MFA_SETUP",
      session: "abc",
    });

    const { rerender } = renderWithRouter(<LoginPage />, {
      route: "/login?next=%2Fjobs",
      path: "/login",
      extraRoutes: [{ path: "/mfa/setup", element: <div>MfaSetup</div> }],
    });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("MfaSetup")).toBeInTheDocument();
    expect(auth.setSession).not.toHaveBeenCalled();
    rerender(<></>);
  });

  it("routes to MFA code challenge when Cognito requests SOFTWARE_TOKEN_MFA", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoLogin.mockResolvedValueOnce({
      status: "CHALLENGE",
      next_step: "SOFTWARE_TOKEN_MFA",
      session: "abc",
    });

    renderWithRouter(<LoginPage />, {
      route: "/login",
      path: "/login",
      extraRoutes: [{ path: "/mfa/code", element: <div>MfaCode</div> }],
    });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("MfaCode")).toBeInTheDocument();
    expect(auth.setSession).not.toHaveBeenCalled();
  });

  it("shows toast on login failure", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoLogin.mockRejectedValueOnce(new Error("Invalid email or password"));

    renderWithRouter(<LoginPage />, { route: "/login", path: "/login" });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "bad");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    // This message shows both inline and as a toast; just assert it's present.
    expect((await screen.findAllByText("Invalid email or password")).length).toBeGreaterThan(0);
  });
});


