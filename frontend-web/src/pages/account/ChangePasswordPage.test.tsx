import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ChangePasswordPage } from "./index";
import { renderWithRouter } from "../../test/testUtils";

const api = vi.hoisted(() => ({
  changePassword: vi.fn(),
}));

vi.mock("../../api", () => ({
  changePassword: api.changePassword,
}));

const auth = vi.hoisted(() => ({
  logout: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => auth,
}));

const currentUser = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
}));

vi.mock("../../hooks/useCurrentUser", () => ({
  useCurrentUser: () => currentUser.useCurrentUser(),
}));

describe("ChangePasswordPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser.useCurrentUser.mockReturnValue({
      user: { email: "test@example.com", name: "Test User", must_change_password: false },
      loading: false,
      error: "",
      reload: vi.fn(),
      isStub: false,
    });
    api.changePassword.mockResolvedValue({ message: "Password updated. Please log in again." });
    auth.logout.mockResolvedValue(undefined);
  });

  it("blocks weak passwords client-side", async () => {
    const user = userEvent.setup();
    renderWithRouter(<ChangePasswordPage />, { route: "/change-password", path: "/change-password" });

    await user.type(screen.getByLabelText("Current password"), "test_password_123");
    await user.type(screen.getByPlaceholderText(/At least/), "password");
    await user.type(screen.getByPlaceholderText("Re-enter new password"), "password");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(api.changePassword).not.toHaveBeenCalled();
    expect((await screen.findAllByText("Please enter your current password and a stronger new password.")).length).toBeGreaterThan(0);
  });

  it("renders backend violations when API returns WEAK_PASSWORD", async () => {
    const user = userEvent.setup();
    api.changePassword.mockRejectedValueOnce(
      Object.assign(new Error("weak"), { detail: { code: "WEAK_PASSWORD", violations: ["denylist_common"] } })
    );

    renderWithRouter(<ChangePasswordPage />, { route: "/change-password", path: "/change-password" });

    await user.type(screen.getByLabelText("Current password"), "test_password_123");
    await user.type(screen.getByPlaceholderText(/At least/), "Password_12345!");
    await user.type(screen.getByPlaceholderText("Re-enter new password"), "Password_12345!");
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getAllByText("Cannot be a common password").length).toBeGreaterThan(0);
  });

  it("shows expiration banner when user must change password", () => {
    currentUser.useCurrentUser.mockReturnValue({
      user: { email: "test@example.com", name: "Test User", must_change_password: true },
      loading: false,
      error: "",
      reload: vi.fn(),
      isStub: false,
    });

    renderWithRouter(<ChangePasswordPage />, { route: "/change-password", path: "/change-password" });

    expect(screen.getByText("Your password has expired. Please update it to continue.")).toBeInTheDocument();
  });
});

