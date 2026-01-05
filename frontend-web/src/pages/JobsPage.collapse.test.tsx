import type React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../components/ui/ToastProvider";
import { CurrentUserProvider } from "../context/CurrentUserContext";
import type { UseCurrentUserResult } from "../hooks/useCurrentUser";

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
  getJobDetails: vi.fn(),
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
  updateUiPreferences: vi.fn(),
};

vi.mock("../api", () => api);

const emptyActivityPage = { items: [], next_cursor: null };

const ToggleStub = ({ label, collapsed, onToggleCollapse }: { label: string; collapsed: boolean; onToggleCollapse?: () => void }) => (
  <button type="button" onClick={onToggleCollapse} disabled={!onToggleCollapse} data-testid={`toggle-${label}`}>
    {collapsed ? `Expand ${label}` : `Collapse ${label}`}
  </button>
);

vi.mock("../components/documents/DocumentsPanel", () => ({
  default: (props: { collapsed: boolean; onToggleCollapse?: () => void }) => <ToggleStub label="documents" {...props} />,
}));
vi.mock("../components/jobs/NotesCard", () => ({
  default: (props: { collapsed: boolean; onToggleCollapse?: () => void }) => <ToggleStub label="notes" {...props} />,
}));
vi.mock("../components/jobs/TimelineCard", () => ({
  default: (props: { collapsed: boolean; onToggleCollapse?: () => void }) => <ToggleStub label="timeline" {...props} />,
}));
vi.mock("../components/jobs/InterviewsCard", () => ({
  default: (props: { collapsed: boolean; onToggleCollapse?: () => void }) => <ToggleStub label="interviews" {...props} />,
}));

vi.mock("../components/jobs/JobDetailsCard", () => ({
  default: () => <div data-testid="JobDetailsCard" />,
}));
vi.mock("../components/jobs/JobCard", () => ({
  default: () => <div>Job form stub</div>,
}));

const baseUser: UseCurrentUserResult = {
  user: {
    id: 1,
    email: "test@example.com",
    name: "Tester",
    auto_refresh_seconds: 0,
    created_at: new Date().toISOString(),
    is_email_verified: true,
    ui_preferences: {},
  },
  loading: false,
  error: "",
  reload: vi.fn().mockResolvedValue(),
  isStub: false,
};

async function renderPage(overrides?: Partial<UseCurrentUserResult["user"]>) {
  window.scrollTo = vi.fn() as typeof window.scrollTo;
  globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  }) as typeof globalThis.requestAnimationFrame;

  const mod = (await import("./JobsPage")) as unknown as { default: React.ComponentType };
  const JobsPage = mod.default;

  const value: UseCurrentUserResult = {
    ...baseUser,
    user: { ...baseUser.user!, ...(overrides ?? {}) },
  };

  return render(
    <ToastProvider>
      <CurrentUserProvider value={value}>
        <JobsPage />
      </CurrentUserProvider>
    </ToastProvider>
  );
}

describe("JobsPage collapse persistence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSavedViews.mockResolvedValue([]);
    api.listJobs.mockResolvedValue([
      {
        id: 1,
        company_name: "Acme",
        job_title: "Engineer",
        location: "Remote",
        status: "applied",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
        tags: [],
      },
    ]);
    api.getJob.mockResolvedValue(null);
    api.getJobDetails.mockResolvedValue({
      job: null,
      notes: [],
      interviews: [],
      activity: emptyActivityPage,
    });
    api.listNotes.mockResolvedValue([]);
    api.listJobActivity.mockResolvedValue(emptyActivityPage);
    api.listInterviews.mockResolvedValue([]);
  });

  it("hydrates collapsed state from ui_preferences", async () => {
    await renderPage({
      ui_preferences: { job_details_notes_collapsed: true },
    });

    expect(screen.getByTestId("toggle-notes")).toHaveTextContent("Expand notes");
  });

  it("persists collapse toggles via updateUiPreferences", async () => {
    const user = userEvent.setup();
    api.updateUiPreferences.mockResolvedValue({ ui_preferences: { job_details_notes_collapsed: true } });

    await renderPage();
    const toggle = await screen.findByTestId("toggle-notes");
    expect(toggle).toHaveTextContent("Collapse notes");

    await user.click(toggle);

    expect(api.updateUiPreferences).toHaveBeenCalledWith({
      preferences: { job_details_notes_collapsed: true },
    });
  });
});


