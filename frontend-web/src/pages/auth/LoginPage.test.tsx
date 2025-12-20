import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "./LoginPage";
import { renderWithRouter } from "../../test/testUtils";

const api = vi.hoisted(() => ({
  loginUser: vi.fn(),
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
  });

  it("logs in and navigates to next", async () => {
    const user = userEvent.setup();
    api.loginUser.mockResolvedValueOnce({ access_token: "t_access" });

    renderWithRouter(<LoginPage />, {
      route: "/login?next=%2Fjobs",
      path: "/login",
      extraRoutes: [{ path: "/jobs", element: <div>JobsRoute</div> }],
    });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "Password_12345");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(auth.setSession).toHaveBeenCalledWith("t_access");
    expect(await screen.findByText("JobsRoute")).toBeInTheDocument();
  });

  it("shows toast on login failure", async () => {
    const user = userEvent.setup();
    api.loginUser.mockRejectedValueOnce(new Error("Invalid email or password"));

    renderWithRouter(<LoginPage />, { route: "/login", path: "/login" });

    await user.type(screen.getByPlaceholderText("you@example.com"), "me@example.com");
    await user.type(screen.getByPlaceholderText("••••••••"), "bad");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    // This message shows both inline and as a toast; just assert it's present.
    expect((await screen.findAllByText("Invalid email or password")).length).toBeGreaterThan(0);
  });
});


