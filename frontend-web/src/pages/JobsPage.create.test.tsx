import type React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../components/ui/ToastProvider";

// Keep most panels stubbed; use real JobCard inside modal.
vi.mock("../hooks/useSettings", () => {
  return {
    useSettings: () => ({
      settings: {
        autoRefreshSeconds: 0,
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

async function renderPage() {
  window.scrollTo = vi.fn() as typeof window.scrollTo;
  globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  }) as typeof globalThis.requestAnimationFrame;

  const mod = (await import("./JobsPage")) as unknown as { default: React.ComponentType };
  const JobsPage = mod.default;

  return render(
    <ToastProvider>
      <JobsPage />
    </ToastProvider>
  );
}

describe("JobsPage (create job)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSavedViews.mockResolvedValue([]);
    api.listJobs.mockResolvedValue([]);
    api.listNotes.mockResolvedValue([]);
    api.listJobActivity.mockResolvedValue([]);
    api.listInterviews.mockResolvedValue([]);
  });

  it("creates a job and closes modal", async () => {
    const user = userEvent.setup();

    const created = {
      id: 1,
      company_name: "Acme",
      job_title: "Engineer",
      location: null,
      job_url: null,
      status: "applied",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_activity_at: new Date().toISOString(),
      tags: [],
    };

    api.createJob.mockResolvedValueOnce(created);
    api.getJob.mockResolvedValueOnce(created);

    await renderPage();

    await user.click(screen.getByRole("button", { name: "+ Add job" }));
    expect(screen.getByRole("dialog", { name: "Add job" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Company name"), "Acme");
    await user.type(screen.getByPlaceholderText("Job title"), "Engineer");
    await user.click(screen.getByRole("button", { name: "Create Job" }));

    await waitFor(() =>
      expect(api.createJob).toHaveBeenCalledWith({
        company_name: "Acme",
        job_title: "Engineer",
        location: null,
        job_url: null,
      })
    );

    expect(await screen.findByText("Job created.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Add job" })).toBeNull());
  });

  it("shows toast error and keeps modal open on create failure", async () => {
    const user = userEvent.setup();
    api.createJob.mockRejectedValueOnce(new Error("Create failed"));

    await renderPage();
    await user.click(screen.getByRole("button", { name: "+ Add job" }));

    await user.type(screen.getByPlaceholderText("Company name"), "Acme");
    await user.type(screen.getByPlaceholderText("Job title"), "Engineer");
    await user.click(screen.getByRole("button", { name: "Create Job" }));

    expect((await screen.findAllByText("Create failed")).length).toBeGreaterThan(0);
    expect(screen.getByRole("dialog", { name: "Add job" })).toBeInTheDocument();
  });
});


