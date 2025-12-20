import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import FiltersPanel from "./FiltersPanel";

describe("FiltersPanel", () => {
  it("calls onSelectTagSuggestion when Enter is pressed", async () => {
    const user = userEvent.setup();
    const onSelectTagSuggestion = vi.fn();

    render(
      <FiltersPanel
        selectedTags={[]}
        onRemoveTag={() => {}}
        tagQuery={"py"}
        onTagQueryChange={() => {}}
        tagSuggestions={["python", "pydantic"]}
        tagFilterOpen={true}
        onTagFilterOpenChange={() => {}}
        onSelectTagSuggestion={onSelectTagSuggestion}
        onClearTagFilter={() => {}}
        view="all"
        viewCounts={{ all: 1, active: 1, needs_followup: 0 }}
        onSelectView={() => {}}
        selectedStatuses={[]}
        statusCounts={{ applied: 1, interviewing: 0, offer: 0, rejected: 0 }}
        onToggleStatus={() => {}}
      />
    );

    const input = screen.getByPlaceholderText("Search tags… (Enter to add)");
    await user.click(input);
    await user.keyboard("{Enter}");
    expect(onSelectTagSuggestion).toHaveBeenCalledWith("python");
  });
});


