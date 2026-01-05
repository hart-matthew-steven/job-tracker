import { describe, it, expect } from "vitest";
import type { JobsBoardResponse } from "../types/api";
import { moveBoardCard } from "./boardState";

describe("moveBoardCard", () => {
  const snapshot: JobsBoardResponse = {
    statuses: ["applied", "interviewing"],
    jobs: [
      {
        id: 1,
        status: "applied",
        company_name: "Acme",
        job_title: "Engineer",
        location: null,
        updated_at: "",
        last_activity_at: null,
        priority: "normal",
        tags: [],
        needs_follow_up: false,
      },
      {
        id: 2,
        status: "interviewing",
        company_name: "Globex",
        job_title: "Designer",
        location: null,
        updated_at: "",
        last_activity_at: null,
        priority: "normal",
        tags: [],
        needs_follow_up: false,
      },
    ],
    meta: {},
  };

  it("updates the status of the matching card", () => {
    const next = moveBoardCard(snapshot, 1, "interviewing");
    expect(next?.jobs.find((j) => j.id === 1)?.status).toBe("interviewing");
  });

  it("returns the original snapshot if the card is missing", () => {
    const next = moveBoardCard(snapshot, 99, "applied");
    expect(next).toBe(snapshot);
  });
});

