import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AIAssistantPage from "./AIAssistantPage";
import type { AiConversationDetail, AiConversationSummary } from "../../types/api";

const api = vi.hoisted(() => ({
  listAiConversations: vi.fn(),
  getAiConversation: vi.fn(),
  createAiConversation: vi.fn(),
  sendAiConversationMessage: vi.fn(),
  getAiConfig: vi.fn(),
  deleteAiConversation: vi.fn(),
  renameAiConversation: vi.fn(),
}));

vi.mock("../../api", () => ({
  listAiConversations: (...args: unknown[]) => api.listAiConversations(...args),
  getAiConversation: (...args: unknown[]) => api.getAiConversation(...args),
  createAiConversation: (...args: unknown[]) => api.createAiConversation(...args),
  sendAiConversationMessage: (...args: unknown[]) => api.sendAiConversationMessage(...args),
  getAiConfig: (...args: unknown[]) => api.getAiConfig(...args),
  deleteAiConversation: (...args: unknown[]) => api.deleteAiConversation(...args),
  renameAiConversation: (...args: unknown[]) => api.renameAiConversation(...args),
}));

const creditsHook = vi.hoisted(() => ({
  useCredits: vi.fn(),
}));

vi.mock("../../hooks/useCredits", () => ({
  useCredits: () => creditsHook.useCredits(),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <AIAssistantPage />
    </MemoryRouter>
  );
}

const baseDetail: AiConversationDetail = {
  id: 1,
  title: "Cover letter thread",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  messages: [],
  next_offset: null,
};

describe("AIAssistantPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    creditsHook.useCredits.mockReturnValue({
      balance: {
        balance_cents: 1000,
        balance_dollars: "$10.00",
        currency: "usd",
        lifetime_granted_cents: 1000,
        lifetime_spent_cents: 0,
        as_of: new Date().toISOString(),
      },
      loading: false,
      error: null,
      refresh: vi.fn(),
    });
    api.listAiConversations.mockResolvedValue({
      conversations: [],
      next_offset: null,
    });
    api.getAiConversation.mockResolvedValue(baseDetail);
    api.createAiConversation.mockResolvedValue({ ...baseDetail, messages: [] });
    api.sendAiConversationMessage.mockResolvedValue({
      conversation_id: 1,
      user_message: {
        id: 1,
        role: "user",
        content_text: "Hi",
        created_at: new Date().toISOString(),
      },
      assistant_message: {
        id: 2,
        role: "assistant",
        content_text: "Hello!",
        created_at: new Date().toISOString(),
        prompt_tokens: 10,
        completion_tokens: 20,
        total_tokens: 30,
        credits_charged: 25,
        balance_remaining_cents: 975,
      },
      credits_used_cents: 25,
      credits_refunded_cents: 0,
      credits_reserved_cents: 25,
      credits_remaining_cents: 975,
      credits_remaining_dollars: "$9.75",
    });
    api.getAiConfig.mockResolvedValue({ max_input_chars: 4000 });
    api.deleteAiConversation.mockResolvedValue(undefined);
    api.renameAiConversation.mockResolvedValue(baseDetail);
  });

  it("renders AI Assistant screen", async () => {
    renderPage();
    expect(await screen.findByText("AI Assistant")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Share job context/i)).toBeInTheDocument();
  });

  it("loads conversation list items", async () => {
    const summary: AiConversationSummary = {
      id: 42,
      title: "Thank you follow-up",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 2,
    };
    api.listAiConversations.mockResolvedValue({
      conversations: [summary],
      next_offset: null,
    });
    api.getAiConversation.mockResolvedValue({ ...baseDetail, id: 42, title: summary.title, messages: [] });

    renderPage();

    expect(await screen.findByText("Thank you follow-up")).toBeInTheDocument();
  });

  it("shows insufficient credit CTA", async () => {
    const user = userEvent.setup();
    api.createAiConversation.mockRejectedValueOnce(Object.assign(new Error("Insufficient credits"), { status: 402 }));

    renderPage();

    const textarea = await screen.findByPlaceholderText(/Share job context/i);
    await user.type(textarea, "Help me tailor my resume");
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect(await screen.findByText(/do not have enough credits/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Buy credits/i })).toBeInTheDocument();
  });

  it("displays per-response metadata", async () => {
    const summary: AiConversationSummary = {
      id: 7,
      title: "Resume polish",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 2,
    };
    api.listAiConversations.mockResolvedValue({
      conversations: [summary],
      next_offset: null,
    });
    api.getAiConversation.mockResolvedValue({
      ...baseDetail,
      id: 7,
      title: summary.title,
      messages: [
        {
          id: 1,
          role: "user",
          content_text: "Need help tightening bullet points.",
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          role: "assistant",
          content_text: "Focus on impact and quantify results.",
          created_at: new Date().toISOString(),
          prompt_tokens: 50,
          completion_tokens: 25,
          total_tokens: 75,
          credits_charged: 30,
          balance_remaining_cents: 970,
        },
      ],
      next_offset: null,
    });

    renderPage();

    expect(await screen.findByText(/Tokens: 50 in \/ 25 out \(75 total\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Credits: \$0\.30/)).toBeInTheDocument();
    expect(screen.getByText(/Remaining: \$9\.70/)).toBeInTheDocument();
  });

  it("applies backend max input character setting", async () => {
    api.getAiConfig.mockResolvedValueOnce({ max_input_chars: 9000 });
    renderPage();
    const textarea = await screen.findByPlaceholderText(/Share job context/i);
    expect((textarea as HTMLTextAreaElement).maxLength).toBe(9000);
  });

  it("lets users delete a conversation", async () => {
    const summary: AiConversationSummary = {
      id: 55,
      title: "Delete me",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    };
    api.listAiConversations.mockResolvedValue({
      conversations: [summary],
      next_offset: null,
    });
    api.getAiConversation.mockResolvedValue({ ...baseDetail, id: 55, title: summary.title, messages: [] });

    const user = userEvent.setup();
    renderPage();

    const actionButton = await screen.findByLabelText("Conversation actions");
    await user.click(actionButton);
    const deleteButton = await screen.findByRole("button", { name: "Delete" });
    await user.click(deleteButton);
    const confirmBtn = await screen.findByRole("button", { name: "Delete" });
    await user.click(confirmBtn);

    await waitFor(() => expect(api.deleteAiConversation).toHaveBeenCalledWith(55));
  });

  it("renames a conversation", async () => {
    const summary: AiConversationSummary = {
      id: 60,
      title: "Original",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0,
    };
    api.listAiConversations.mockResolvedValue({
      conversations: [summary],
      next_offset: null,
    });
    api.getAiConversation.mockResolvedValue({ ...baseDetail, id: 60, title: summary.title, messages: [] });
    api.renameAiConversation.mockResolvedValue({ ...baseDetail, id: 60, title: "Updated" });

    const user = userEvent.setup();
    renderPage();

    const actionButton = await screen.findByLabelText("Conversation actions");
    await user.click(actionButton);
    const renameButton = await screen.findByRole("button", { name: "Rename" });
    await user.click(renameButton);

    const input = await screen.findByLabelText("Title");
    await user.clear(input);
    await user.type(input, "Updated");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.renameAiConversation).toHaveBeenCalledWith(60, { title: "Updated" }));
    expect(await screen.findByText("Updated")).toBeInTheDocument();
  });
});
