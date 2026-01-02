import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RegisterPage from "./RegisterPage";
import { renderWithRouter } from "../../test/testUtils";

const cognitoApi = vi.hoisted(() => ({
  cognitoSignup: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);

const turnstileCallbacks: {
  success?: (token: string) => void;
  error?: () => void;
} = {};

function setupTurnstileMock() {
  turnstileCallbacks.success = undefined;
  turnstileCallbacks.error = undefined;
  window.turnstile = {
    render: vi.fn((_, options: Record<string, unknown>) => {
      turnstileCallbacks.success = options.callback as (token: string) => void;
      turnstileCallbacks.error = options["error-callback"] as () => void;
      return "widget-id";
    }),
    execute: vi.fn(() => {
      turnstileCallbacks.success?.("turnstile-token");
    }),
    reset: vi.fn(),
  };
}

describe("RegisterPage", () => {
  // api mocks are hoisted; clear call history per test
  beforeEach(() => {
    vi.clearAllMocks();
    window.__TURNSTILE_SITE_KEY__ = "site-key";
    setupTurnstileMock();
  });

  it("registers and navigates to verify page", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoSignup.mockResolvedValueOnce({ message: "Account created." });

    renderWithRouter(<RegisterPage />, {
      route: "/register?next=%2Fjobs",
      path: "/register",
      extraRoutes: [{ path: "/verify", element: <div>VerifyRoute</div> }],
    });

    await user.type(screen.getByPlaceholderText("Your name"), "Matt");
    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.type(screen.getByPlaceholderText(/At least/), "Password_12345");
    await user.type(screen.getByPlaceholderText("Repeat password"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("VerifyRoute")).toBeInTheDocument();
    expect((await screen.findAllByText(/Account created/)).length).toBeGreaterThan(0);
    expect(cognitoApi.cognitoSignup).toHaveBeenCalledWith({
      email: "matt@example.com",
      name: "Matt",
      password: "Password_12345",
      turnstile_token: "turnstile-token",
    });
  });

  it("blocks weak passwords client-side and shows requirements", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.type(screen.getByPlaceholderText("Your name"), "Matt");
    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.type(screen.getByPlaceholderText(/At least/), "password");
    await user.type(screen.getByPlaceholderText("Repeat password"), "password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(cognitoApi.cognitoSignup).not.toHaveBeenCalled();
    expect(screen.getAllByText(/At least 14 characters/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/At least 14 characters/).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Cannot be a common password")).length).toBeGreaterThan(0);
  });

  it("renders backend violations when API returns WEAK_PASSWORD", async () => {
    const user = userEvent.setup();
    cognitoApi.cognitoSignup.mockRejectedValueOnce(
      Object.assign(new Error("weak"), {
        detail: { code: "WEAK_PASSWORD", violations: ["uppercase", "number"] },
      })
    );

    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.type(screen.getByPlaceholderText("Your name"), "Matt");
    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.type(screen.getByPlaceholderText(/At least/), "Password_12345");
    await user.type(screen.getByPlaceholderText("Repeat password"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(cognitoApi.cognitoSignup).toHaveBeenCalled();
    expect((await screen.findAllByText("Cannot be a common password")).length).toBeGreaterThan(0);
  });

  it("blocks submission when passwords mismatch and shows toast", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.type(screen.getByPlaceholderText("Your name"), "Matt");
    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.type(screen.getByPlaceholderText(/At least/), "Password_12345");
    await user.type(screen.getByPlaceholderText("Repeat password"), "Password_00000");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(cognitoApi.cognitoSignup).not.toHaveBeenCalled();
    expect((await screen.findAllByText("Passwords do not match.")).length).toBeGreaterThan(0);
  });

  it("disables signup when Turnstile is not configured", () => {
    window.__TURNSTILE_SITE_KEY__ = "";
    window.turnstile = undefined;

    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    expect(screen.getByText(/bot verification is not configured/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });
});

