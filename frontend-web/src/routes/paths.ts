export const ROUTES = {
  // Public
  home: "/",
  login: "/login",
  register: "/register",
  demoBoard: "/demo/board",
  verify: "/verify",
  mfaSetup: "/mfa/setup",
  mfaChallenge: "/mfa/code",

  // App (protected)
  dashboard: "/board",
  board: "/board",
  jobs: "/jobs",
  insights: "/insights",
  billing: "/billing",
  billingReturn: "/billing/return",
  billingReturnSuccessLegacy: "/billing/stripe/success",
  billingReturnCanceledLegacy: "/billing/stripe/cancelled",

  // Account (protected)
  profile: "/profile",
  settings: "/settings",
  changePassword: "/change-password",
} as const;


