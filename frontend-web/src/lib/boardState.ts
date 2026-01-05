import type { JobsBoardResponse } from "../types/api";

export function moveBoardCard(
  snapshot: JobsBoardResponse | null,
  jobId: number,
  nextStatus: string
): JobsBoardResponse | null {
  if (!snapshot) return snapshot;
  let changed = false;
  const jobs = snapshot.jobs.map((card) => {
    if (card.id !== jobId) return card;
    changed = true;
    return { ...card, status: nextStatus };
  });
  if (!changed) return snapshot;
  return { ...snapshot, jobs };
}

