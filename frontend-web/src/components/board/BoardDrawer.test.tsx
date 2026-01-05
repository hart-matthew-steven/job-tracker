import { describe, it, expect, beforeEach, afterEach, vi, type Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BoardDrawer } from "./BoardDrawer";
import { ToastProvider } from "../ui/ToastProvider";
import type { JobDetailsBundle } from "../../types/api";
import {
  getJobDetails,
  listJobActivity,
  patchJob,
} from "../../api";

vi.mock("../../api", () => ({
  getJobDetails: vi.fn(),
  listJobActivity: vi.fn(),
  patchJob: vi.fn(),
  addNote: vi.fn(),
  deleteNote: vi.fn(),
  createInterview: vi.fn(),
  deleteInterview: vi.fn(),
}));

vi.mock("../jobs/NotesCard", () => ({ default: () => <div data-testid="notes-card" /> }));
vi.mock("../jobs/InterviewsCard", () => ({ default: () => <div data-testid="interviews-card" /> }));
vi.mock("../jobs/TimelineCard", () => ({ default: () => <div data-testid="timeline-card" /> }));
vi.mock("../documents/DocumentsPanel", () => ({ default: () => <div data-testid="documents-panel" /> }));

const sampleBundle: JobDetailsBundle = {
  job: {
    id: 1,
    company_name: "Acme Corp",
    job_title: "Frontend Engineer",
    status: "applied",
    location: "Remote",
    job_url: "https://example.com/job",
    updated_at: "2026-01-05T09:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    priority: "normal",
    tags: [],
    last_action_at: null,
    next_action_at: null,
    next_action_title: null,
  },
  notes: [],
  interviews: [],
  activity: { items: [], next_cursor: null },
};

beforeEach(() => {
  (getJobDetails as unknown as Mock).mockResolvedValue(sampleBundle);
  (listJobActivity as unknown as Mock).mockResolvedValue({ items: [], next_cursor: null });
  (patchJob as unknown as Mock).mockResolvedValue({
    id: 1,
    status: "interviewing",
    updated_at: "2026-01-05T10:00:00Z",
    last_action_at: "2026-01-05T09:00:00Z",
    next_action_at: null,
    next_action_title: null,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  document.body.classList.remove("drawer-open");
});

describe("BoardDrawer", () => {
  it("renders nothing when closed", () => {
    const { queryByText } = render(
      <ToastProvider>
        <BoardDrawer jobId={null} onClose={() => undefined} onCardUpdate={() => undefined} onRefreshBoard={() => undefined} open={false} />
      </ToastProvider>
    );
    expect(queryByText(/Details/)).toBeNull();
  });

  it("updates status exactly once and patches server-side", async () => {
    const user = userEvent.setup();
    const onCardUpdate = vi.fn();
    render(
      <ToastProvider>
        <BoardDrawer jobId={1} onClose={() => undefined} onCardUpdate={onCardUpdate} onRefreshBoard={() => undefined} open />
      </ToastProvider>
    );

    await waitFor(() => expect(getJobDetails).toHaveBeenCalledWith(1));

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "interviewing");

    await waitFor(() => expect(patchJob).toHaveBeenCalledTimes(1));
    expect(patchJob).toHaveBeenCalledWith(1, { status: "interviewing" });
    expect(onCardUpdate).toHaveBeenCalledTimes(2); // optimistic + confirmed
    expect(onCardUpdate.mock.calls[0][0]).toMatchObject({ id: 1, status: "interviewing" });
    expect(onCardUpdate.mock.calls[1][0]).toMatchObject({
      id: 1,
      status: "interviewing",
      updated_at: "2026-01-05T10:00:00Z",
      last_action_at: "2026-01-05T09:00:00Z",
    });
    expect(getJobDetails).toHaveBeenCalledTimes(1);
  });

  it("toggles the drawer-open body class based on visibility", async () => {
    const { rerender } = render(
      <ToastProvider>
        <BoardDrawer jobId={1} onClose={() => undefined} onCardUpdate={() => undefined} onRefreshBoard={() => undefined} open />
      </ToastProvider>
    );

    await waitFor(() => expect(getJobDetails).toHaveBeenCalled());
    expect(document.body.classList.contains("drawer-open")).toBe(true);

    rerender(
      <ToastProvider>
        <BoardDrawer jobId={1} onClose={() => undefined} onCardUpdate={() => undefined} onRefreshBoard={() => undefined} open={false} />
      </ToastProvider>
    );

    await waitFor(() => expect(document.body.classList.contains("drawer-open")).toBe(false));
  });
});

