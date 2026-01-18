// src/App.tsx
import { BrowserRouter, Route, Routes, Navigate, useNavigate } from "react-router-dom";
import { useEffect } from "react";

import DashboardPage from "./pages/DashboardPage";
import JobsPage from "./pages/JobsPage";
import BoardPage from "./pages/BoardPage";
import BillingPage from "./pages/billing/BillingPage";
import BillingReturnPage from "./pages/billing/BillingReturnPage";
import AIAssistantPage from "./pages/ai/AIAssistantPage";

import { useAuth } from "./auth/AuthProvider";
import { subscribeToEmailVerificationRequired } from "./api";
import RequireAuth from "./auth/RequireAuth";

import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import VerifyEmailPage from "./pages/auth/VerifyEmailPage";
import AuthShellLayout from "./pages/auth/AuthShellLayout";
import RedirectIfAuthed from "./pages/auth/RedirectIfAuthed";
import MfaSetupPage from "./pages/auth/MfaSetupPage";
import MfaChallengePage from "./pages/auth/MfaChallengePage";

import AppShell from "./components/layout/AppShell";
import ApiEventListener from "./components/layout/ApiEventListener";
import { ChangePasswordPage, ProfilePage, SettingsPage } from "./pages/account";
import { ROUTES } from "./routes/paths";
import LandingPage from "./pages/landing/LandingPage";
import DemoBoardPage from "./pages/landing/DemoBoardPage";

function EmailVerificationListener() {
  const navigate = useNavigate();
  useEffect(() => {
    return subscribeToEmailVerificationRequired((info) => {
      const params = new URLSearchParams();
      if (info?.email) params.set("email", info.email);
      navigate(`/verify?${params.toString()}`, { replace: false });
    });
  }, [navigate]);
  return null;
}

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
      <EmailVerificationListener />
      <ApiEventListener />
      <Routes>
        <Route path={ROUTES.home} element={<LandingPage />} />
        <Route path={ROUTES.demoBoard} element={<DemoBoardPage />} />

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
          <Route path={ROUTES.mfaSetup} element={<MfaSetupPage />} />
          <Route path={ROUTES.mfaChallenge} element={<MfaChallengePage />} />
        </Route>

        <Route element={<AuthShellLayout />}>
          <Route path={ROUTES.verify} element={<VerifyEmailPage />} />
        </Route>

        {/* Protected app routes */}
        <Route
          element={
            <RequireAuth>
              <AppShell onLogout={logout} />
            </RequireAuth>
          }
        >
          <Route path={ROUTES.board} element={<BoardPage />} />
          <Route path={ROUTES.jobs} element={<JobsPage />} />
          <Route path={ROUTES.insights} element={<DashboardPage />} />
          <Route path={ROUTES.aiAssistant} element={<AIAssistantPage />} />
          <Route path={ROUTES.billing} element={<BillingPage />} />
          <Route path={ROUTES.billingReturn} element={<BillingReturnPage />} />
          <Route path={ROUTES.billingReturnSuccessLegacy} element={<BillingReturnPage />} />
          <Route path={ROUTES.billingReturnCanceledLegacy} element={<BillingReturnPage />} />
          <Route path={ROUTES.profile} element={<ProfilePage />} />
          <Route path={ROUTES.settings} element={<SettingsPage />} />
          <Route path={ROUTES.changePassword} element={<ChangePasswordPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to={ROUTES.board} replace />} />
      </Routes>
    </BrowserRouter>
  );
}


