import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MfaChallengePage from "./MfaChallengePage";
import { renderWithRouter } from "../../test/testUtils";

const cognitoApi = vi.hoisted(() => ({
  cognitoRespondToChallenge: vi.fn(),
}));

vi.mock("../../api/authCognito", () => cognitoApi);

const auth = vi.hoisted(() => ({
  setSession: vi.fn(),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => auth,
}));

describe("MfaChallengePage", () => {
  it("submits MFA code and stores session", async () => {
    cognitoApi.cognitoRespondToChallenge.mockResolvedValueOnce({
      status: "OK",
      tokens: { access_token: "tok", expires_in: 3600, token_type: "Bearer" },
    });

    renderWithRouter(<MfaChallengePage />, {
      route: { pathname: "/mfa/code", state: { email: "me@example.com", session: "sess1", next: "/jobs" } },
      path: "/mfa/code",
      extraRoutes: [{ path: "/jobs", element: <div>Jobs</div> }],
    });

    await userEvent.type(screen.getByPlaceholderText("6-digit code"), "123456");
    await userEvent.click(screen.getByRole("button", { name: "Verify & continue" }));

    await waitFor(() =>
      expect(cognitoApi.cognitoRespondToChallenge).toHaveBeenCalledWith({
        email: "me@example.com",
        challenge_name: "SOFTWARE_TOKEN_MFA",
        session: "sess1",
        responses: {
          USERNAME: "me@example.com",
          SOFTWARE_TOKEN_MFA_CODE: "123456",
        },
      })
    );
    expect(auth.setSession).toHaveBeenCalledWith({
      access_token: "tok",
      expires_in: 3600,
      token_type: "Bearer",
    });
  });
});

