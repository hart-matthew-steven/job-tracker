import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommandMenu } from "./CommandMenu";

vi.mock("../../api", () => ({
  searchBoardJobs: vi.fn().mockResolvedValue({ statuses: [], jobs: [], meta: {} }),
}));

describe("CommandMenu", () => {
  it("renders when open and closes on overlay click", () => {
    const onClose = vi.fn();
    render(<CommandMenu open onClose={onClose} onSelect={vi.fn()} />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("textbox"));
    const overlay = document.querySelector('[aria-hidden="true"]');
    if (overlay) {
      fireEvent.click(overlay);
    }
    expect(onClose).toHaveBeenCalled();
  });

  it("invokes onSelect when a result is clicked", async () => {
    const { searchBoardJobs } = await import("../../api");
    const searchBoardJobsMock = vi.mocked(searchBoardJobs);
    searchBoardJobsMock.mockResolvedValueOnce({
      statuses: [],
      jobs: [
        {
          id: 1,
          status: "applied",
          company_name: "Acme",
          job_title: "Eng",
          location: null,
          updated_at: "",
          last_activity_at: null,
          priority: "normal",
          tags: [],
          needs_follow_up: false,
        },
      ],
      meta: {},
    });
    const onSelect = vi.fn();
    render(<CommandMenu open onClose={vi.fn()} onSelect={onSelect} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Acme" } });
    await screen.findByText(/Acme/);
    fireEvent.click(screen.getByText(/Acme/));
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});

