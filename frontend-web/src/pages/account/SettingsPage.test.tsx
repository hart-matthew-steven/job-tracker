import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../../components/ui/ToastProvider";
import { SettingsPage } from "./index";

const api = vi.hoisted(() => ({
  getMySettings: vi.fn(),
  updateMySettings: vi.fn(),
}));

vi.mock("../../api", () => api);

function renderPage() {
  return render(
    <ToastProvider>
      <SettingsPage />
    </ToastProvider>
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMySettings.mockResolvedValue({
      auto_refresh_seconds: 0,
      theme: "dark",
      default_jobs_sort: "updated_desc",
      default_jobs_view: "all",
      data_retention_days: 0,
    });
    api.updateMySettings.mockResolvedValue({ message: "Settings updated" });

    document.documentElement.classList.remove("dark");
    document.documentElement.removeAttribute("data-theme");
  });

  it("applies theme immediately on change", async () => {
    const user = userEvent.setup();
    renderPage();

    // After initial load, theme should apply to document.
    // (useSettings applies theme whenever settings.theme changes)
    await screen.findByText("Preferences");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    // Change to Light
    const selects = screen.getAllByRole("combobox");
    const themeSelect = selects.find((s) => (s as HTMLSelectElement).value === "dark") as HTMLSelectElement;
    expect(themeSelect).toBeTruthy();

    await user.selectOptions(themeSelect, "light");

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    expect(api.updateMySettings).toHaveBeenCalled();
    const payload = api.updateMySettings.mock.calls.at(-1)?.[0];
    expect(payload).toMatchObject({ theme: "light" });
  });

  it("shows toast on auto-refresh update failure", async () => {
    const user = userEvent.setup();
    api.updateMySettings.mockRejectedValueOnce(new Error("nope"));

    renderPage();
    await screen.findByText("Preferences");

    // Auto refresh frequency select: default is 0/off
    const selects = screen.getAllByRole("combobox");
    const autoRefreshSelect = selects.find((s) => (s as HTMLSelectElement).value === "0") as HTMLSelectElement;
    expect(autoRefreshSelect).toBeTruthy();

    await user.selectOptions(autoRefreshSelect, "10");

    // Error is rendered both inline and as toast; just assert it exists.
    expect((await screen.findAllByText("nope")).length).toBeGreaterThan(0);
  });

  it("updates default jobs sort + view and calls updateMySettings", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Preferences");

    const selects = screen.getAllByRole("combobox") as HTMLSelectElement[];
    const sortSelect = selects.find((s) => s.value === "updated_desc");
    const viewSelect = selects.find((s) => s.value === "all");
    expect(sortSelect).toBeTruthy();
    expect(viewSelect).toBeTruthy();

    await user.selectOptions(sortSelect!, "company_asc");
    await user.selectOptions(viewSelect!, "active");

    const calls = api.updateMySettings.mock.calls.map((c) => c[0]);
    expect(calls.some((p) => p?.default_jobs_sort === "company_asc")).toBe(true);
    expect(calls.some((p) => p?.default_jobs_view === "active")).toBe(true);
  });

  it("updates Hide jobs after (days) and calls updateMySettings", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Preferences");

    const input = screen.getByLabelText("Hide jobs after (days)") as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "365");

    // last call should include data_retention_days: 365
    const payload = api.updateMySettings.mock.calls.at(-1)?.[0];
    expect(payload).toMatchObject({ data_retention_days: 365 });
  });
});


