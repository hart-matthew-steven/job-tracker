// src/App.tsx
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";

import DashboardPage from "./pages/DashboardPage";
import JobsPage from "./pages/JobsPage";

import { useAuth } from "./auth/AuthProvider";
import RequireAuth from "./auth/RequireAuth";

import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import VerifyEmailPage from "./pages/auth/VerifyEmailPage";
import AuthShellLayout from "./pages/auth/AuthShellLayout";
import RedirectIfAuthed from "./pages/auth/RedirectIfAuthed";
import MfaSetupPage from "./pages/auth/MfaSetupPage";
import MfaChallengePage from "./pages/auth/MfaChallengePage";

import AppShell from "./components/layout/AppShell";
import { ChangePasswordPage, ProfilePage, SettingsPage } from "./pages/account";
import { ROUTES } from "./routes/paths";

export default function App() {
  const { isReady, logout } = useAuth();

  if (!isReady) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-sm text-slate-400">Loading…</div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        {/* Auth routes */}
        <Route
          element={
            <RedirectIfAuthed>
              <AuthShellLayout />
            </RedirectIfAuthed>
          }
        >
          <Route path={ROUTES.login} element={<LoginPage />} />
          <Route path={ROUTES.register} element={<RegisterPage />} />
          <Route path={ROUTES.verify} element={<VerifyEmailPage />} />
          <Route path={ROUTES.mfaSetup} element={<MfaSetupPage />} />
          <Route path={ROUTES.mfaChallenge} element={<MfaChallengePage />} />
        </Route>

        {/* Protected app routes */}
        <Route
          element={
            <RequireAuth>
              <AppShell onLogout={logout} />
            </RequireAuth>
          }
        >
          <Route path={ROUTES.dashboard} element={<DashboardPage />} />
          <Route path={ROUTES.jobs} element={<JobsPage />} />
          <Route path={ROUTES.profile} element={<ProfilePage />} />
          <Route path={ROUTES.settings} element={<SettingsPage />} />
          <Route path={ROUTES.changePassword} element={<ChangePasswordPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to={ROUTES.dashboard} replace />} />
      </Routes>
    </BrowserRouter>
  );
}


