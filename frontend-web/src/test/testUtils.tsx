/* eslint-disable react-refresh/only-export-components */
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { MemoryRouterProps } from "react-router-dom";
import { render } from "@testing-library/react";

import { ToastProvider } from "../components/ui/ToastProvider";

export function LocationDisplay() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname}{loc.search}</div>;
}

export function renderWithRouter(
  ui: ReactElement,
  opts: {
    route: string | NonNullable<MemoryRouterProps["initialEntries"]>[number];
    path: string;
    extraRoutes?: Array<{ path: string; element: ReactElement }>;
  }
) {
  const { route, path, extraRoutes = [] } = opts;
  const initialEntry = typeof route === "string" ? route : route;
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path={path} element={ui} />
          {extraRoutes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
          <Route path="*" element={<LocationDisplay />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  );
}


