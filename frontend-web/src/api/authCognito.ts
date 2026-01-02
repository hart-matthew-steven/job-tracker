import { requestJson, requestVoid } from "../api";
import type {
  CognitoAuthResponse,
  CognitoChallengeRequest,
  CognitoMessage,
  CognitoMfaSetupIn,
  CognitoMfaVerifyIn,
  CognitoSignupIn,
  CognitoConfirmIn,
  CognitoRefreshIn,
} from "../types/api";

function jsonOptions(body: unknown) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function cognitoSignup(payload: CognitoSignupIn): Promise<CognitoMessage> {
  return requestJson<CognitoMessage>("/auth/cognito/signup", jsonOptions(payload));
}

export function cognitoConfirm(payload: CognitoConfirmIn): Promise<CognitoMessage> {
  return requestJson<CognitoMessage>("/auth/cognito/confirm", jsonOptions(payload));
}

export function cognitoLogin(email: string, password: string): Promise<CognitoAuthResponse> {
  return requestJson<CognitoAuthResponse>("/auth/cognito/login", jsonOptions({ email, password }));
}

export function cognitoRespondToChallenge(payload: CognitoChallengeRequest): Promise<CognitoAuthResponse> {
  return requestJson<CognitoAuthResponse>("/auth/cognito/challenge", jsonOptions(payload));
}

export function cognitoMfaSetup(payload: CognitoMfaSetupIn) {
  return requestJson<{ secret_code: string; otpauth_uri?: string; session?: string }>("/auth/cognito/mfa/setup", jsonOptions(payload));
}

export function cognitoMfaVerify(payload: CognitoMfaVerifyIn): Promise<CognitoAuthResponse> {
  return requestJson<CognitoAuthResponse>("/auth/cognito/mfa/verify", jsonOptions(payload));
}

export function cognitoRefresh(payload: CognitoRefreshIn): Promise<CognitoAuthResponse> {
  return requestJson<CognitoAuthResponse>("/auth/cognito/refresh", jsonOptions(payload));
}

export function cognitoLogout(): Promise<void> {
  return requestVoid("/auth/cognito/logout", { method: "POST" });
}

