import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import JobsList from "./JobsList";

describe("JobsList", () => {
  it("renders jobs and calls onSelectJob when clicked", async () => {
    const user = userEvent.setup();
    const onSelectJob = vi.fn();

    render(
      <JobsList
        jobs={[
          {
            id: 1,
            company_name: "Apple",
            job_title: "Lead Engineer",
            last_activity_at: new Date().toISOString(),
          },
        ]}
        selectedJobId={null}
        onSelectJob={onSelectJob}
      />
    );

    expect(screen.getByText("Apple — Lead Engineer")).toBeInTheDocument();
    await user.click(screen.getByRole("button"));
    expect(onSelectJob).toHaveBeenCalledTimes(1);
    expect(onSelectJob.mock.calls[0]?.[0]?.id).toBe(1);
  });
});


