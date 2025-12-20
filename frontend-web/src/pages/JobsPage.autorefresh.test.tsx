import type React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ToastProvider } from "../components/ui/ToastProvider";

vi.mock("../hooks/useSettings", () => {
  return {
    useSettings: () => ({
      settings: {
        autoRefreshSeconds: 1,
        dataRetentionDays: 0,
        defaultJobsSort: "updated_desc",
        defaultJobsView: "all",
      },
      loading: false,
    }),
  };
});

const api = {
  listJobs: vi.fn(),
  getJob: vi.fn(),
  createJob: vi.fn(),
  patchJob: vi.fn(),
  listNotes: vi.fn(),
  addNote: vi.fn(),
  deleteNote: vi.fn(),
  createSavedView: vi.fn(),
  deleteSavedView: vi.fn(),
  listSavedViews: vi.fn(),
  patchSavedView: vi.fn(),
  listJobActivity: vi.fn(),
  createInterview: vi.fn(),
  deleteInterview: vi.fn(),
  listInterviews: vi.fn(),
};

vi.mock("../api", () => api);

vi.mock("../components/documents/DocumentsPanel", () => ({
  default: () => <div data-testid="DocumentsPanel" />,
}));
vi.mock("../components/jobs/NotesCard", () => ({
  default: () => <div data-testid="NotesCard" />,
}));
vi.mock("../components/jobs/JobDetailsCard", () => ({
  default: () => <div data-testid="JobDetailsCard" />,
}));
vi.mock("../components/jobs/TimelineCard", () => ({
  default: () => <div data-testid="TimelineCard" />,
}));
vi.mock("../components/jobs/InterviewsCard", () => ({
  default: () => <div data-testid="InterviewsCard" />,
}));
vi.mock("../components/jobs/JobCard", () => ({
  default: () => <div>Job form stub</div>,
}));

async function renderPage() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).scrollTo = vi.fn();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).requestAnimationFrame = (cb: (t: number) => void) => {
    cb(0);
    return 0;
  };

  const mod = (await import("./JobsPage")) as unknown as { default: React.ComponentType };
  const JobsPage = mod.default;

  return render(
    <ToastProvider>
      <JobsPage />
    </ToastProvider>
  );
}

describe("JobsPage (auto-refresh)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    api.listSavedViews.mockResolvedValue([]);
    api.listJobs.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("auto refresh calls listJobs on interval when not paused", async () => {
    await renderPage();

    // Allow initial refresh + debounce to settle, then start counting fresh.
    await vi.advanceTimersByTimeAsync(400);
    api.listJobs.mockClear();

    await vi.advanceTimersByTimeAsync(1100);
    expect(api.listJobs).toHaveBeenCalled();
  });

  it("does not auto refresh when document is hidden", async () => {
    await renderPage();
    await vi.advanceTimersByTimeAsync(400);
    api.listJobs.mockClear();

    Object.defineProperty(document, "hidden", { value: true, configurable: true });
    await vi.advanceTimersByTimeAsync(1100);
    expect(api.listJobs).not.toHaveBeenCalled();

    Object.defineProperty(document, "hidden", { value: false, configurable: true });
  });

  it("does not auto refresh while typing in an input", async () => {
    await renderPage();
    await vi.advanceTimersByTimeAsync(400);
    api.listJobs.mockClear();

    const search = screen.getByPlaceholderText("Company, title, location…");
    search.focus();

    await vi.advanceTimersByTimeAsync(1100);
    expect(api.listJobs).not.toHaveBeenCalled();
  });

  it("does not auto refresh when a modal is open", async () => {
    await renderPage();
    await vi.advanceTimersByTimeAsync(400);
    api.listJobs.mockClear();

    fireEvent.click(screen.getByRole("button", { name: "+ Add job" }));
    expect(screen.getByRole("dialog", { name: "Add job" })).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(1100);
    expect(api.listJobs).not.toHaveBeenCalled();
  });
});


