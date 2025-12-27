// src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { applyThemeToDocument, getInitialTheme } from "./lib/theme";

import App from "./App";
import AuthProvider from "./auth/AuthProvider";
import { ToastProvider } from "./components/ui/ToastProvider";

applyThemeToDocument(getInitialTheme());

const el = document.getElementById("root");
if (!el) throw new Error("Missing #root element");

createRoot(el).render(
  <StrictMode>
    <ToastProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ToastProvider>
  </StrictMode>
);


