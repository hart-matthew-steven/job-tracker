import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MfaSetupPage from "./MfaSetupPage";
import { renderWithRouter } from "../../test/testUtils";

const cognitoApi = vi.hoisted(() => ({
  cognitoMfaSetup: vi.fn(),
  cognitoMfaVerify: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);

vi.mock("qrcode", () => ({
  toDataURL: vi.fn(() => Promise.resolve("data:image/png;base64,qr")),
}));

const auth = vi.hoisted(() => ({
  setSession: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => auth,
}));

describe("MfaSetupPage", () => {
  it("fetches secret, renders QR, and verifies code", async () => {
    cognitoApi.cognitoMfaSetup.mockResolvedValueOnce({
      secret_code: "SECRET123",
      otpauth_uri: "otpauth://foo",
      session: "sess2",
    });
    cognitoApi.cognitoMfaVerify.mockResolvedValueOnce({
      status: "OK",
      tokens: { access_token: "tok", expires_in: 3600, token_type: "Bearer" },
    });

    renderWithRouter(<MfaSetupPage />, {
      route: { pathname: "/mfa/setup", state: { email: "me@example.com", session: "sess1", next: "/jobs" } },
      path: "/mfa/setup",
      extraRoutes: [{ path: "/jobs", element: <div>Jobs</div> }],
    });

    await waitFor(() => expect(cognitoApi.cognitoMfaSetup).toHaveBeenCalledWith({ session: "sess1", label: "JobTracker:me@example.com" }));

    expect(await screen.findByText(/SECRET123/)).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify & continue" }));

    await waitFor(() =>
      expect(cognitoApi.cognitoMfaVerify).toHaveBeenCalledWith({
        email: "me@example.com",
        session: "sess2",
        code: "123456",
        friendly_name: "JobTracker",
      })
    );
    expect(auth.setSession).toHaveBeenCalledWith({
      access_token: "tok",
      expires_in: 3600,
      token_type: "Bearer",
    });
  });
});

