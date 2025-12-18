export const ROUTES = {
  // Auth (public)
  login: "/login",
  register: "/register",
  verify: "/verify",

  // App (protected)
  dashboard: "/",
  jobs: "/jobs",

  // Account (protected)
  profile: "/profile",
  settings: "/settings",
  changePassword: "/change-password",
} as const;


