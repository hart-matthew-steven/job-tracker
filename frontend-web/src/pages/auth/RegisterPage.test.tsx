import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RegisterPage from "./RegisterPage";
import { renderWithRouter } from "../../test/testUtils";

const api = vi.hoisted(() => ({
  registerUser: vi.fn(),
  resendVerification: vi.fn(),
}));

vi.mock("../../api", () => api);

describe("RegisterPage", () => {
  // api mocks are hoisted; clear call history per test
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("registers and navigates to verify page", async () => {
    const user = userEvent.setup();
    api.registerUser.mockResolvedValueOnce({ message: "Registered. Please verify your email." });

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
    expect((await screen.findAllByText("Registered. Please verify your email.")).length).toBeGreaterThan(0);
  });

  it("blocks weak passwords client-side and shows requirements", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.type(screen.getByPlaceholderText("Your name"), "Matt");
    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.type(screen.getByPlaceholderText(/At least/), "password");
    await user.type(screen.getByPlaceholderText("Repeat password"), "password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(api.registerUser).not.toHaveBeenCalled();
    expect(screen.getAllByText(/At least 14 characters/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/At least 14 characters/).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Cannot be a common password")).length).toBeGreaterThan(0);
  });

  it("renders backend violations when API returns WEAK_PASSWORD", async () => {
    const user = userEvent.setup();
    api.registerUser.mockRejectedValueOnce(
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

    expect(api.registerUser).toHaveBeenCalled();
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

    expect(api.registerUser).not.toHaveBeenCalled();
    expect((await screen.findAllByText("Passwords do not match.")).length).toBeGreaterThan(0);
  });

  it("resend verification requires email", async () => {
    const user = userEvent.setup();
    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.click(screen.getByRole("button", { name: "Resend verification" }));
    expect((await screen.findAllByText("Enter your email above first.")).length).toBeGreaterThan(0);
  });

  it("resends verification and shows info toast", async () => {
    const user = userEvent.setup();
    api.resendVerification.mockResolvedValueOnce({ message: "If that email exists, a verification link was sent." });

    renderWithRouter(<RegisterPage />, { route: "/register", path: "/register" });

    await user.type(screen.getByPlaceholderText("you@example.com"), "matt@example.com");
    await user.click(screen.getByRole("button", { name: "Resend verification" }));

    expect(api.resendVerification).toHaveBeenCalledWith({ email: "matt@example.com" });
    expect((await screen.findAllByText("If that email exists, a verification link was sent.")).length).toBeGreaterThan(0);
  });
});


