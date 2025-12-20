import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import RequireAuth from "./RequireAuth";
import { LocationDisplay } from "../test/testUtils";

const auth = vi.hoisted(() => ({
  useAuth: vi.fn(),
}));

vi.mock("./AuthProvider", () => ({
  useAuth: () => auth.useAuth(),
}));

function renderRoutes(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route
          path="/jobs"
          element={
            <RequireAuth>
              <div>JobsProtected</div>
            </RequireAuth>
          }
        />
        <Route path="/login" element={<LocationDisplay />} />
        <Route path="*" element={<LocationDisplay />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RequireAuth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    try {
      sessionStorage.clear();
    } catch {
      // ignore
    }
  });

  it("shows loading while auth is hydrating", async () => {
    auth.useAuth.mockReturnValue({ isReady: false, isAuthenticated: false });
    renderRoutes("/jobs?x=1");
    expect(await screen.findByText("Loading…")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to /login?next=...", async () => {
    auth.useAuth.mockReturnValue({ isReady: true, isAuthenticated: false });
    renderRoutes("/jobs?x=1");
    expect(await screen.findByTestId("location")).toHaveTextContent("/login?next=%2Fjobs%3Fx%3D1");
  });

  it("redirects to /login (no next) when jt.justLoggedOut flag is set", async () => {
    auth.useAuth.mockReturnValue({ isReady: true, isAuthenticated: false });
    sessionStorage.setItem("jt.justLoggedOut", "1");
    renderRoutes("/jobs?x=1");
    expect(await screen.findByTestId("location")).toHaveTextContent("/login");
  });

  it("renders children when authenticated", async () => {
    auth.useAuth.mockReturnValue({ isReady: true, isAuthenticated: true });
    renderRoutes("/jobs");
    expect(await screen.findByText("JobsProtected")).toBeInTheDocument();
  });
});


