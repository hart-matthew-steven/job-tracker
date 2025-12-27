import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ToastProvider } from "../components/ui/ToastProvider";

// ---- Mocks (keep JobsPage test focused on JobsPage logic, not child panels) ----
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
vi.mock("../components/jobs/JobCard", () => ({
    default: () => <div>Job form stub</div>,
}));

async function renderPage() {
    // JobsPage uses requestAnimationFrame + scrollTo.
    // JSDOM doesn't reliably implement these.
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

describe("JobsPage", () => {
    beforeEach(() => {
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
        api.listNotes.mockResolvedValue([]);
        api.listJobActivity.mockResolvedValue([]);
        api.listInterviews.mockResolvedValue([]);
        try {
            window.localStorage?.clear?.();
        } catch {
            // ignore
        }
    });

    afterEach(() => {
        // Safety: if any test enabled fake timers (and then failed), ensure we don't leak into later tests.
        vi.useRealTimers();
        vi.clearAllMocks();
    });

    it("calls listJobs on mount, and again (debounced) when search changes", async () => {
        vi.useFakeTimers();
        try {
            await renderPage();

            // Initial load(s). StrictMode / effects can cause more than one call, so only assert on the latest args.
            expect(api.listJobs).toHaveBeenCalled();
            expect(api.listJobs.mock.calls.at(-1)?.[0]).toMatchObject({ q: "", tag_q: "", tag: [], status: [] });

            // Let any mount-time debounce settle so our baseline is stable.
            await act(async () => {
                await vi.runOnlyPendingTimersAsync();
            });

            const callsAfterMount = api.listJobs.mock.calls.length;

            // Debounced refresh after changing search
            const search = screen.getByPlaceholderText("Company, title, location…");
            fireEvent.change(search, { target: { value: "Acme" } });

            await act(async () => {
                await vi.advanceTimersByTimeAsync(260);
            });

            expect(api.listJobs.mock.calls.length).toBeGreaterThan(callsAfterMount);
            expect(api.listJobs.mock.calls.at(-1)?.[0]).toMatchObject({ q: "Acme", tag_q: "", tag: [], status: [] });
        } finally {
            vi.useRealTimers();
        }
    });

    it("toggles a status chip and refreshes jobs (debounced) with status[]", async () => {
        const user = userEvent.setup();
        await renderPage();

        // JobsPage triggers an initial load and also has a debounced "filters changed" effect
        // that can fire shortly after mount. Let it settle, then start assertions from a clean slate.
        await new Promise((r) => setTimeout(r, 300));
        api.listJobs.mockClear();

        const applied = screen
            .getAllByRole("button", { name: /Applied/i })
            .find((b) => b.getAttribute("title") === "Filter jobs by status (multi-select)");
        expect(applied).toBeTruthy();
        await user.click(applied!);
        await new Promise((r) => setTimeout(r, 300));

        expect(api.listJobs).toHaveBeenCalledTimes(1);
        expect(api.listJobs.mock.calls[0]?.[0]).toMatchObject({ status: ["applied"] });

        // Toggle off
        await user.click(applied!);
        await new Promise((r) => setTimeout(r, 300));

        expect(api.listJobs).toHaveBeenCalledTimes(2);
        expect(api.listJobs.mock.calls[1]?.[0]).toMatchObject({ status: [] });
    });

    it("opens the Add job modal when + Add job is clicked", async () => {
        const user = userEvent.setup();
        await renderPage();

        const add = screen
            .getAllByRole("button", { name: "+ Add job" })
            .find((b) => b.getAttribute("title") === "Add a new job");
        expect(add).toBeTruthy();
        await user.click(add!);
        expect(screen.getByRole("dialog", { name: "Add job" })).toBeInTheDocument();
        expect(screen.getByText("Job form stub")).toBeInTheDocument();
    });

    it("shows a toast if saved views fail to load", async () => {
        api.listSavedViews.mockRejectedValueOnce(new Error("boom"));
        await renderPage();

        // ToastProvider renders toast content into the DOM.
        expect(await screen.findByText("boom")).toBeInTheDocument();
    });

    it("clicking Use defaults clears filters and refreshes jobs", async () => {
        const user = userEvent.setup();
        await renderPage();

        // Let initial effects settle then start clean
        await new Promise((r) => setTimeout(r, 300));
        api.listJobs.mockClear();

        await user.type(screen.getByPlaceholderText("Company, title, location…"), "Acme");
        await new Promise((r) => setTimeout(r, 300));
        api.listJobs.mockClear();

        await user.click(screen.getByRole("button", { name: "Use defaults" }));
        await new Promise((r) => setTimeout(r, 300));

        expect(api.listJobs).toHaveBeenCalled();
        const last = api.listJobs.mock.calls.at(-1)?.[0] ?? {};
        expect(last).toMatchObject({ q: "", tag_q: "", tag: [], status: [] });
        expect(await screen.findByText("Applied account defaults.")).toBeInTheDocument();
    });

    it("tag filter Enter selects first suggestion and refreshes with tag[]", async () => {
        const user = userEvent.setup();

        // Keep returning tagged jobs even as the page triggers additional debounced refreshes.
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
                tags: ["python", "backend"],
            },
        ]);

        await renderPage();

        await new Promise((r) => setTimeout(r, 300));
        api.listJobs.mockClear();

        const input = screen.getByPlaceholderText("Search tags… (Enter to add)");
        await user.click(input);
        await user.type(input, "py");
        await user.keyboard("{Enter}");

        // Wait until we see a call that reflects the added tag (typing triggers tag_q calls too).
        await waitFor(() => {
            const ok = api.listJobs.mock.calls.some((c) => {
                const arg = c?.[0] ?? {};
                const tags = (arg as { tag?: unknown }).tag;
                const tagQ = (arg as { tag_q?: unknown }).tag_q;
                return Array.isArray(tags) && tags.includes("python") && (tagQ === "" || tagQ === undefined);
            });
            expect(ok).toBe(true);
        });
    });

    it("saved views: save, apply, delete", async () => {
        const user = userEvent.setup();

        api.listSavedViews.mockResolvedValueOnce([
            {
                id: 10,
                name: "My Saved",
                data: { search: "Globex", tags: ["python"], statuses: ["applied"], view: "all", sortMode: "updated_desc", tagQuery: "" },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]);

        api.createSavedView.mockResolvedValueOnce({
            id: 11,
            name: "New View",
            data: {},
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });

        api.deleteSavedView.mockResolvedValueOnce({ message: "ok" });

        await renderPage();

        await user.click(
            screen.getAllByRole("button", { name: "Views" }).find((b) => b.getAttribute("title") === "Manage saved views")!
        );

        expect(screen.getByRole("dialog", { name: "Saved views" })).toBeInTheDocument();

        // Save current view first
        await user.type(screen.getByPlaceholderText("View name (e.g. Remote + follow-up)"), "New View");
        await user.click(screen.getByRole("button", { name: "Save" }));
        expect(api.createSavedView).toHaveBeenCalledWith(expect.objectContaining({ name: "New View" }));
        expect(await screen.findByText("Saved view created.")).toBeInTheDocument();

        // Apply existing view
        const rowTitle = await screen.findByText("My Saved");
        const row = rowTitle.parentElement?.parentElement; // min-w-0 -> row container
        expect(row).toBeTruthy();
        await user.click(within(row!).getByRole("button", { name: "Apply" }));
        expect(await screen.findByText(/Applied "My Saved"\./)).toBeInTheDocument();
        expect(screen.getByPlaceholderText("Company, title, location…")).toHaveValue("Globex");

        // Re-open modal (apply closes it)
        await user.click(
            screen.getAllByRole("button", { name: "Views" }).find((b) => b.getAttribute("title") === "Manage saved views")!
        );
        expect(screen.getByRole("dialog", { name: "Saved views" })).toBeInTheDocument();

        // Delete existing view
        const rowTitle2 = await screen.findByText("My Saved");
        const row2 = rowTitle2.parentElement?.parentElement;
        expect(row2).toBeTruthy();
        await user.click(within(row2!).getByRole("button", { name: "Delete" }));
        await waitFor(() => expect(api.deleteSavedView).toHaveBeenCalledWith(10));
        expect(await screen.findByText("Saved view deleted.")).toBeInTheDocument();
    });

    it("saved view save overwrites on name conflict", async () => {
        const user = userEvent.setup();

        api.listSavedViews.mockResolvedValueOnce([
            {
                id: 10,
                name: "My View",
                data: { search: "", tags: [], statuses: [], view: "all", sortMode: "updated_desc", tagQuery: "" },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]);

        api.createSavedView.mockRejectedValueOnce(new Error("A saved view with that name already exists"));
        api.patchSavedView.mockResolvedValueOnce({
            id: 10,
            name: "My View",
            data: { search: "Acme" },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        });

        await renderPage();

        await user.click(
            screen.getAllByRole("button", { name: "Views" }).find((b) => b.getAttribute("title") === "Manage saved views")!
        );

        await user.type(screen.getByPlaceholderText("View name (e.g. Remote + follow-up)"), "My View");
        await user.click(screen.getByRole("button", { name: "Save" }));

        await waitFor(() => expect(api.patchSavedView).toHaveBeenCalledWith(10, expect.anything()));
        expect(await screen.findByText("Saved view updated.")).toBeInTheDocument();
    });

    it("selecting a job loads details (getJob/notes/activity/interviews)", async () => {
        const user = userEvent.setup();

        api.listJobs.mockResolvedValueOnce([
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
        api.getJob.mockResolvedValueOnce({
            id: 1,
            company_name: "Acme",
            job_title: "Engineer",
            location: "Remote",
            status: "applied",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            last_activity_at: new Date().toISOString(),
            tags: [],
        });
        api.listNotes.mockResolvedValueOnce([]);
        api.listJobActivity.mockResolvedValueOnce([]);
        api.listInterviews.mockResolvedValueOnce([]);

        await renderPage();
        const label = await screen.findByText("Acme — Engineer");
        const btn = label.closest("button");
        expect(btn).toBeTruthy();
        await user.click(btn!);

        await waitFor(() => expect(api.getJob).toHaveBeenCalledWith(1));
        expect(api.listNotes).toHaveBeenCalledWith(1);
        expect(api.listJobActivity).toHaveBeenCalledWith(1, expect.anything());
        expect(api.listInterviews).toHaveBeenCalledWith(1);
    });
});


