import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AuthProvider, { useAuth } from "./AuthProvider";

const mockedLogout = vi.hoisted(() => vi.fn());

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    logoutUser: mockedLogout,
  };
});

function LogoutTester() {
  const auth = useAuth();
  return (
    <div>
      <div data-testid="authed">{auth.isAuthenticated ? "yes" : "no"}</div>
      <button type="button" onClick={() => auth.logout()}>
        Logout
      </button>
    </div>
  );
}

describe("AuthProvider logout", () => {
  afterEach(() => {
    sessionStorage.clear();
    mockedLogout.mockReset();
  });

  it("clears session storage and calls backend logout", async () => {
    sessionStorage.setItem(
      "jt.auth.session",
      JSON.stringify({
        accessToken: "tok",
        refreshToken: "ref",
        tokenType: "Bearer",
        expiresAt: Date.now() + 60_000,
      })
    );
    window.dispatchEvent(new StorageEvent("storage", { key: "jt.auth.session", newValue: sessionStorage.getItem("jt.auth.session") }));
    mockedLogout.mockResolvedValueOnce(undefined);

    render(
      <AuthProvider>
        <LogoutTester />
      </AuthProvider>
    );

    expect(screen.getByTestId("authed")).toHaveTextContent("yes");

    await userEvent.click(screen.getByRole("button", { name: "Logout" }));

    expect(mockedLogout).toHaveBeenCalled();
    expect(sessionStorage.getItem("jt.auth.session")).toBeNull();
    expect(screen.getByTestId("authed")).toHaveTextContent("no");
  });
});

