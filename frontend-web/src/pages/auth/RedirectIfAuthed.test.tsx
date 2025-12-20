import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import RedirectIfAuthed from "./RedirectIfAuthed";
import { LocationDisplay } from "../../test/testUtils";

const auth = vi.hoisted(() => ({
  useAuth: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => auth.useAuth(),
}));

describe("RedirectIfAuthed", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children when not authenticated", async () => {
    auth.useAuth.mockReturnValue({ isAuthenticated: false });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route
            path="/login"
            element={
              <RedirectIfAuthed>
                <div>LoginForm</div>
              </RedirectIfAuthed>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("LoginForm")).toBeInTheDocument();
  });

  it("redirects authenticated users to next or /", async () => {
    auth.useAuth.mockReturnValue({ isAuthenticated: true });
    render(
      <MemoryRouter initialEntries={["/login?next=%2Fjobs"]}>
        <Routes>
          <Route
            path="/login"
            element={
              <RedirectIfAuthed>
                <div>LoginForm</div>
              </RedirectIfAuthed>
            }
          />
          <Route path="/jobs" element={<div>JobsRoute</div>} />
          <Route path="*" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("JobsRoute")).toBeInTheDocument();
  });
});


