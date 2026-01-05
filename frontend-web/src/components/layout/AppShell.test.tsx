import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { within } from "@testing-library/react";

import AppShell from "./AppShell";
import { LocationDisplay } from "../../test/testUtils";

const currentUser = vi.hoisted(() => ({
  useCurrentUser: vi.fn(),
}));

vi.mock("../../hooks/useCurrentUser", () => ({
  useCurrentUser: () => currentUser.useCurrentUser(),
}));

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser.useCurrentUser.mockReturnValue({
      user: { name: "Matt", email: "matt@example.com" },
      isStub: false,
      loading: false,
      error: "",
      reload: vi.fn(),
    });
  });

  it("navigates via sidebar links", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/board"]}>
        <Routes>
          <Route element={<AppShell onLogout={() => {}} />}>
            <Route path="/board" element={<div>Board</div>} />
            <Route path="/insights" element={<div>Insights</div>} />
          </Route>
          <Route path="*" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    );

    const main = screen.getByRole("main");
    expect(within(main).getByText("Board")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Insights" }));
    expect(within(main).getByText("Insights")).toBeInTheDocument();
  });

  it("account menu logout calls onLogout and routes to home", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn().mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={["/jobs"]}>
        <Routes>
          <Route element={<AppShell onLogout={onLogout} />}>
            <Route path="/jobs" element={<div>Jobs</div>} />
          </Route>
          <Route path="/" element={<div>Home</div>} />
          <Route path="*" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    );

    // Open account menu (button shows user name on desktop, but we can query by aria-haspopup)
    await user.click(screen.getByRole("button", { name: /Matt|Account/i }));
    expect(screen.getByRole("menu", { name: "Account" })).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: "Logout" }));
    expect(onLogout).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Home")).toBeInTheDocument();
  });

  it("redirects to change password when user must rotate credentials", async () => {
    currentUser.useCurrentUser.mockReturnValueOnce({
      user: { name: "Matt", email: "matt@example.com", must_change_password: true },
      isStub: false,
      loading: false,
      error: "",
      reload: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/jobs"]}>
        <Routes>
          <Route element={<AppShell onLogout={() => {}} />}>
            <Route path="/jobs" element={<div>Jobs</div>} />
            <Route path="/change-password" element={<div>ChangePasswordRoute</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("ChangePasswordRoute")).toBeInTheDocument();
  });
});


