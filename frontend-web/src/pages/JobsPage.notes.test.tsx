import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../components/ui/ToastProvider";

// Notes-focused JobsPage tests: keep other panels stubbed, but use the real NotesCard.
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

describe("JobsPage (notes)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSavedViews.mockResolvedValue([]);
    api.listInterviews.mockResolvedValue([]);
    api.listJobActivity.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("adds and deletes a note, and refreshes activity", async () => {
    const user = userEvent.setup();

    const job = {
      id: 1,
      company_name: "Acme",
      job_title: "Engineer",
      location: "Remote",
      status: "applied",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_activity_at: new Date().toISOString(),
      tags: [],
    };

    api.listJobs.mockResolvedValue([job]);
    api.getJob.mockResolvedValue(job);

    // notes refresh: first load empty, after add return the created note
    api.listNotes
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 10, body: "hello", created_at: new Date().toISOString() }])
      .mockResolvedValueOnce([]); // after delete

    api.addNote.mockResolvedValueOnce({ id: 10, body: "hello", created_at: new Date().toISOString() });
    api.deleteNote.mockResolvedValueOnce({ message: "ok" });

    await renderPage();

    // Select job to mount NotesCard with handlers wired.
    const label = await screen.findByText("Acme — Engineer");
    await user.click(label.closest("button")!);

    // Add note
    await user.type(await screen.findByPlaceholderText("Add a note..."), "hello");
    await user.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(api.addNote).toHaveBeenCalledWith(1, { body: "hello" }));
    expect(await screen.findByText("Note added.")).toBeInTheDocument();

    // Note appears after refresh
    expect(await screen.findByText("hello")).toBeInTheDocument();

    // Activity refreshed after add
    expect(api.listJobActivity).toHaveBeenCalledWith(1, expect.anything());

    // Delete note
    await user.click(screen.getByTitle("Delete note"));
    await waitFor(() => expect(api.deleteNote).toHaveBeenCalledWith(1, 10));
    expect(await screen.findByText("Note deleted.")).toBeInTheDocument();
  });
});


