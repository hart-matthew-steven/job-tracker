import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { Copy, Loader2, MessageSquare, MoreVertical, NotebookPen, Sparkles } from "lucide-react";

import {
  createAiConversation,
  deleteAiConversation,
  getAiConfig,
  getAiConversation,
  listAiConversations,
  renameAiConversation,
  sendAiConversationMessage,
} from "../../api";
import type {
  AiConversationDetail,
  AiConversationMessageResponse,
  AiConversationSummary,
  AiMessage,
  AiPurpose,
} from "../../types/api";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Modal from "../../components/ui/Modal";
import { useCredits } from "../../hooks/useCredits";
import { ROUTES } from "../../routes/paths";

const PURPOSE_OPTIONS: Array<{
  value: AiPurpose;
  label: string;
  helper: string;
}> = [
  {
    value: "general",
    label: "General chat",
    helper: "Open-ended assistance with no preset framing.",
  },
  {
    value: "cover_letter",
    label: "Cover Letter",
    helper: "Draft a compelling cover letter tailored to the role.",
  },
  {
    value: "thank_you",
    label: "Thank You Letter",
    helper: "Summarize takeaways and gratitude after interviews.",
  },
  {
    value: "resume_tailoring",
    label: "Resume Tailoring (text only)",
    helper: "Iterate on bullet points with quantifiable impact.",
  },
];

type StatusBanner =
  | { type: "insufficient"; message: string }
  | { type: "rate-limit"; message: string }
  | { type: "error"; message: string; retry?: () => void };

type LastSubmission = {
  text: string;
  purpose: AiPurpose;
  conversationId: number | null;
};

function formatCurrency(cents: number | null | undefined): string {
  if (typeof cents !== "number") return "—";
  return (cents / 100).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function summarize(detail: AiConversationDetail): AiConversationSummary {
  return {
    id: detail.id,
    title: detail.title,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    message_count: detail.messages.length,
  };
}

function trimInput(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

export default function AIAssistantPage() {
  const navigate = useNavigate();
  const credits = useCredits();
  const [conversations, setConversations] = useState<AiConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [conversation, setConversation] = useState<AiConversationDetail | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [purpose, setPurpose] = useState<AiPurpose>("general");
  const [composerValue, setComposerValue] = useState("");
  const [sending, setSending] = useState(false);
  const [statusBanner, setStatusBanner] = useState<StatusBanner | null>(null);
  const [deleteBusyId, setDeleteBusyId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: number; title?: string | null } | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const [renameTarget, setRenameTarget] = useState<{ id: number; title?: string | null } | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);
  const [maxInputChars, setMaxInputChars] = useState(2000);
  const lastSubmission = useRef<LastSubmission | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const hasAutoSelected = useRef(false);

  const hasCredits = (credits.balance?.balance_cents ?? 0) > 0;
  const trimmedValue = trimInput(composerValue);
  const canSend = Boolean(trimmedValue) && hasCredits && !sending;

  const refreshConversations = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const data = await listAiConversations({ limit: 25 });
      setConversations(data.conversations);
      if (!hasAutoSelected.current && !activeConversationId && data.conversations.length > 0) {
        hasAutoSelected.current = true;
        setActiveConversationId(data.conversations[0].id);
      }
    } catch (err) {
      const message = (err as Error)?.message || "Unable to load conversations.";
      setListError(message);
    } finally {
      setListLoading(false);
    }
  }, [activeConversationId]);

  const loadConversation = useCallback(
    async (conversationId: number | null) => {
      if (!conversationId) {
        setConversation(null);
        setDetailError(null);
        setDetailLoading(false);
        return;
      }
      setDetailLoading(true);
      setDetailError(null);
      try {
        const data = await getAiConversation(conversationId, { limit: 100 });
        setConversation(data);
      } catch (err) {
        const message = (err as Error)?.message || "Unable to load conversation.";
        setDetailError(message);
      } finally {
        setDetailLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    void loadConversation(activeConversationId);
  }, [activeConversationId, loadConversation]);

  useEffect(() => {
    if (!menuOpenId) return;
    function handleClick(event: MouseEvent) {
      const container = listRef.current;
      if (!container) return;
      const target = event.target as Node | null;
      if (target && container.contains(target)) {
        return;
      }
      setMenuOpenId(null);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpenId]);

  useEffect(() => {
    let active = true;
    getAiConfig()
      .then((config) => {
        if (!active) return;
        setMaxInputChars(config.max_input_chars || 2000);
      })
      .catch(() => {
        // Ignore config errors; fallback stays at default.
      });
    return () => {
      active = false;
    };
  }, []);

  const scrollToBottom = useCallback(() => {
    const node = scrollRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    if (detailLoading) return;
    requestAnimationFrame(() => {
      scrollToBottom();
    });
  }, [detailLoading, conversation?.id, conversation?.messages.length, sending, scrollToBottom]);

  const handleSelectConversation = (conversationId: number) => {
    setActiveConversationId(conversationId);
    setStatusBanner(null);
    setMenuOpenId(null);
  };

  const handleBeginNewConversation = () => {
    setActiveConversationId(null);
    setConversation(null);
    setComposerValue("");
    setStatusBanner(null);
  };

  const handleCopy = async (message: AiMessage) => {
    try {
      await navigator.clipboard.writeText(message.content_text);
    } catch {
      // Swallow copy errors silently.
    }
  };

  const applySummaryUpdate = (summary: AiConversationSummary) => {
    setConversations((prev) => {
      const filtered = prev.filter((item) => item.id !== summary.id);
      return [summary, ...filtered];
    });
  };

  const attachMessagesToConversation = (response: AiConversationMessageResponse) => {
    setConversation((prev: AiConversationDetail | null) =>
      prev
        ? {
            ...prev,
            messages: [...prev.messages, response.user_message, response.assistant_message],
            updated_at: response.assistant_message.created_at,
          }
        : {
            id: response.conversation_id,
            title: null,
            created_at: response.user_message.created_at,
            updated_at: response.assistant_message.created_at,
            messages: [response.user_message, response.assistant_message],
            next_offset: null,
          }
    );
  };

  const startSubmission = (text: string, selectedPurpose: AiPurpose, conversationId: number | null) => {
    lastSubmission.current = { text, purpose: selectedPurpose, conversationId };
    setStatusBanner(null);
  };

  const resetComposerAfterFailure = (text: string, shouldRestore: boolean) => {
    if (shouldRestore) {
      setComposerValue(text);
    }
  };

  const handleSend = async (opts?: {
    overrideText?: string;
    overridePurpose?: AiPurpose;
    overrideConversationId?: number | null;
    skipComposerReset?: boolean;
  }) => {
    const input = opts?.overrideText ?? trimmedValue;
    const targetPurpose = opts?.overridePurpose ?? purpose;
    const conversationId = opts?.overrideConversationId ?? activeConversationId;
    const skipReset = Boolean(opts?.skipComposerReset);
    const payloadPurpose = targetPurpose === "general" ? undefined : targetPurpose;

    const sanitized = trimInput(input);
    if (!sanitized || sending) return;

    startSubmission(sanitized, targetPurpose, conversationId ?? null);
    if (!skipReset) {
      setComposerValue("");
    }

    setSending(true);

    try {
      if (!conversationId) {
        const detail = await createAiConversation({
          title: sanitized.slice(0, 60),
          message: sanitized,
          purpose: payloadPurpose,
        });
        setConversation(detail);
        setActiveConversationId(detail.id);
        applySummaryUpdate(summarize(detail));
      } else {
        const response = await sendAiConversationMessage(conversationId, {
          content: sanitized,
          ...(payloadPurpose ? { purpose: payloadPurpose } : {}),
        });
        attachMessagesToConversation(response);
        applySummaryUpdate({
          id: conversationId,
          title: conversation?.title ?? "Untitled conversation",
          created_at: conversation?.created_at ?? response.user_message.created_at,
          updated_at: response.assistant_message.created_at,
          message_count: (conversation?.messages.length ?? 0) + 2,
        });
      }
      void credits.refresh().catch(() => null);
      lastSubmission.current = null;
    } catch (err) {
      const error = err as Error & { status?: number };
      if (error.status === 402) {
        setStatusBanner({
          type: "insufficient",
          message: "You do not have enough credits to run the AI assistant.",
        });
        resetComposerAfterFailure(sanitized, !skipReset);
      } else if (error.status === 429) {
        setStatusBanner({
          type: "rate-limit",
          message: "Slow down a bit—you're temporarily rate limited. Try again in a few seconds.",
        });
        resetComposerAfterFailure(sanitized, !skipReset);
      } else {
        setStatusBanner({
          type: "error",
          message: error.message || "The AI assistant ran into an issue.",
          retry: lastSubmission.current
            ? () =>
                handleSend({
                  overrideText: lastSubmission.current?.text,
                  overridePurpose: lastSubmission.current?.purpose,
                  overrideConversationId: lastSubmission.current?.conversationId,
                  skipComposerReset: true,
                })
            : undefined,
        });
        resetComposerAfterFailure(sanitized, !skipReset);
      }
    } finally {
      setSending(false);
    }
  };

  const handleComposerSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleSend();
  };

  const handleDeleteConversation = async (conversationId: number, title?: string | null) => {
    setPendingDelete(null);
    setDeleteBusyId(conversationId);
    try {
      await deleteAiConversation(conversationId);
      setConversations((prev) => prev.filter((item) => item.id !== conversationId));
      if (conversationId === activeConversationId) {
        setActiveConversationId(null);
        setConversation(null);
      }
    } catch (err) {
      const message = (err as Error)?.message || "Unable to delete the conversation. Please try again.";
      setStatusBanner({
        type: "error",
        message,
        retry: () => void handleDeleteConversation(conversationId, title),
      });
    } finally {
      setDeleteBusyId((current) => (current === conversationId ? null : current));
    }
  };

  const handleRenameSave = async () => {
    if (!renameTarget) return;
    const sanitized = renameValue.trim();
    setRenameBusy(true);
    try {
      const updated = await renameAiConversation(renameTarget.id, { title: sanitized || null });
      setConversations((prev) =>
        prev.map((item) =>
          item.id === updated.id
            ? {
                ...item,
                title: updated.title,
                updated_at: updated.updated_at,
              }
            : item
        )
      );
      setConversation((prev) => (prev && prev.id === updated.id ? { ...prev, title: updated.title } : prev));
      setRenameTarget(null);
    } catch (err) {
      setStatusBanner({
        type: "error",
        message: (err as Error)?.message || "Unable to rename conversation.",
      });
    } finally {
      setRenameBusy(false);
    }
  };

  const purposeHelper = useMemo(
    () => PURPOSE_OPTIONS.find((option) => option.value === purpose)?.helper ?? "",
    [purpose]
  );

  const showEmptyState = !conversation && !detailLoading && !detailError && !sending;

  return (
    <>
      <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-500">AI Assistant</p>
          <p className="text-sm text-slate-400">Use credits to accelerate offers—no documents required.</p>
        </div>
        <div className="text-xs text-slate-500">
          Credits balance{" "}
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {credits.balance?.balance_dollars ?? "—"}
          </span>
        </div>
      </div>

      <div className="flex h-[70vh] gap-6">
        <aside
          className="flex w-72 flex-col rounded-3xl border border-slate-200 bg-white/70 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/40"
          ref={listRef}
        >
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-100">Conversations</p>
              <p className="text-xs text-slate-400">History never spends credits.</p>
            </div>
            <button
              type="button"
              onClick={handleBeginNewConversation}
              className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-900"
            >
              <Sparkles size={14} />
              New
            </button>
          </div>

          {listError && (
            <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200">
              {listError}
              <button type="button" className="ml-2 underline" onClick={() => void refreshConversations()}>
                Retry
              </button>
            </div>
          )}

          <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
            {listLoading && <p className="text-xs text-slate-400">Loading conversations…</p>}
            {!listLoading && conversations.length === 0 && (
              <p className="text-xs text-slate-400">Start a prompt to create your first conversation.</p>
            )}
            {conversations.map((item) => {
              const isActive = item.id === activeConversationId;
              return (
                <div
                  role="button"
                  tabIndex={0}
                  key={item.id}
                  onClick={() => handleSelectConversation(item.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleSelectConversation(item.id);
                    }
                  }}
                  className={`relative w-full rounded-2xl border px-3 py-2 text-left text-sm transition ${
                    isActive
                      ? "border-slate-900 bg-slate-900 text-white shadow-sm dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                    : "border-transparent bg-slate-100/60 text-slate-600 hover:border-slate-200 hover:bg-white dark:bg-slate-900/30 dark:text-slate-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="line-clamp-1 text-sm font-semibold">
                        {item.title?.trim() || "Untitled conversation"}
                      </p>
                      <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {new Date(item.updated_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          event.preventDefault();
                          setMenuOpenId((prev) => (prev === item.id ? null : item.id));
                        }}
                        aria-label="Conversation actions"
                        className="rounded-full border border-slate-200 bg-white/90 p-1.5 text-slate-600 shadow-sm transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
                      >
                        <MoreVertical size={16} />
                      </button>
                      {menuOpenId === item.id && (
                        <div className="absolute right-0 z-20 mt-2 w-36 rounded-xl border border-slate-200 bg-white p-1 shadow-xl dark:border-slate-700 dark:bg-slate-900">
                          <button
                            type="button"
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                            onClick={(event) => {
                              event.stopPropagation();
                              setMenuOpenId(null);
                              setRenameTarget({ id: item.id, title: item.title });
                              setRenameValue(item.title ?? "");
                            }}
                          >
                            Rename
                          </button>
                          <button
                            type="button"
                            className="block w-full rounded-lg px-3 py-2 text-left text-sm text-rose-600 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-950/40"
                            onClick={(event) => {
                              event.stopPropagation();
                              setMenuOpenId(null);
                              setPendingDelete({ id: item.id, title: item.title });
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        <section className="flex flex-1 flex-col rounded-3xl border border-slate-200 bg-white/80 p-0 shadow-sm dark:border-slate-800 dark:bg-slate-900/40">
          <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-200">
                <Sparkles size={18} />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800 dark:text-white">AI Workspace</p>
                <p className="text-xs text-slate-400">Organized threads, per-response usage, and copy-ready answers.</p>
              </div>
            </div>
            <div className="text-xs text-slate-400">
              Remaining credits
              <div className="text-sm font-semibold text-slate-900 dark:text-white">
                {credits.balance?.balance_dollars ?? "—"}
              </div>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
            {detailError && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
                {detailError} <button onClick={() => void loadConversation(activeConversationId)}>Retry</button>
              </div>
            )}
            {detailLoading && <p className="text-sm text-slate-400">Loading conversation…</p>}
            {showEmptyState && (
              <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50/60 px-6 py-12 text-center dark:border-slate-800 dark:bg-slate-900/30">
                <Sparkles className="mx-auto text-slate-300" size={28} />
                <p className="mt-3 text-sm font-semibold text-slate-600 dark:text-slate-200">No messages yet</p>
                <p className="mt-1 text-sm text-slate-400">
                  Your prompts and AI replies will appear here. Credits are only consumed when you send a prompt.
                </p>
              </div>
            )}
            {conversation?.messages.map((message: AiMessage) => {
              const isAssistant = message.role === "assistant";
              return (
                <article
                  key={message.id}
                  className={`flex flex-col gap-2 rounded-3xl border px-4 py-3 text-sm shadow-sm ${
                    isAssistant
                      ? "border-emerald-200/60 bg-white text-slate-800 dark:border-emerald-900/40 dark:bg-slate-900"
                      : "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900/20"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <span>{isAssistant ? "Assistant" : "You"}</span>
                    <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <p className="whitespace-pre-line text-sm text-slate-900 dark:text-slate-100">{message.content_text}</p>
                  {isAssistant && (
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400">
                      <span>
                        Tokens: {message.prompt_tokens ?? "—"} in / {message.completion_tokens ?? "—"} out (
                        {message.total_tokens ?? "—"} total)
                      </span>
                      <span>Credits: {formatCurrency(message.credits_charged ?? null)}</span>
                      <span>Remaining: {formatCurrency(message.balance_remaining_cents)}</span>
                      <button
                        type="button"
                        onClick={() => void handleCopy(message)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 transition hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                      >
                        <Copy size={12} />
                        Copy
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
            {sending && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="animate-spin" size={16} />
                Generating…
              </div>
            )}
          </div>

          <form onSubmit={handleComposerSubmit} className="space-y-4 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
            {statusBanner && (
              <div
                className={`flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3 text-sm ${
                  statusBanner.type === "insufficient"
                    ? "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200"
                    : statusBanner.type === "rate-limit"
                      ? "bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-200"
                      : "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-200"
                }`}
              >
                <span>{statusBanner.message}</span>
                {statusBanner.type === "insufficient" && (
                  <button
                    type="button"
                    onClick={() => navigate(ROUTES.billing)}
                    className="rounded-full border border-white/40 px-3 py-1 text-xs font-semibold text-slate-900 dark:text-slate-900"
                  >
                    Buy credits
                  </button>
                )}
                {statusBanner.type === "error" && statusBanner.retry && (
                  <button type="button" onClick={statusBanner.retry} className="text-xs font-semibold underline">
                    Retry
                  </button>
                )}
              </div>
            )}

            <div className="grid gap-2 sm:grid-cols-[200px_auto] sm:gap-4">
              <label className="flex flex-col text-xs font-semibold text-slate-500">
                Template (optional)
                <select
                  value={purpose}
                  onChange={(event) => setPurpose(event.target.value as AiPurpose)}
                  className="mt-1 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  {PURPOSE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <span className="mt-1 text-[11px] font-normal text-slate-400">{purposeHelper}</span>
              </label>

              <div>
                <textarea
                  value={composerValue}
                  onChange={(event) => setComposerValue(event.target.value)}
                  placeholder="Share job context, target tone, or paste snippets…"
                  rows={3}
                  maxLength={maxInputChars}
                  className="w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 placeholder:text-slate-300 focus:border-slate-500 focus:outline-none dark:border-slate-700 dark:bg-slate-950/60 dark:text-slate-100"
                />
                <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                  <button
                    type="button"
                    disabled
                    className="inline-flex items-center gap-1 text-slate-400 transition disabled:opacity-60"
                    title="Draft saving coming soon"
                  >
                    <NotebookPen size={12} />
                    Save as draft
                  </button>
                  <span>
                    {trimmedValue.length}/{maxInputChars}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <button
                type="submit"
                disabled={!canSend}
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white shadow-sm transition enabled:hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-900 dark:enabled:hover:bg-white"
              >
                {sending && <Loader2 size={14} className="animate-spin" />}
                <MessageSquare size={14} />
                Send
              </button>
            </div>
            {!hasCredits && (
              <p className="text-xs text-amber-600">
                You need prepaid credits to send prompts. Purchase a pack from{" "}
                <NavLink to={ROUTES.billing} className="underline">
                  billing
                </NavLink>
                .
              </p>
            )}
          </form>
        </section>
      </div>
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete conversation?"
        body={
          <p>
            This will permanently remove{" "}
            <span className="font-semibold">{pendingDelete?.title?.trim() || "this conversation"}</span>. This action
            cannot be undone.
          </p>
        }
        confirmLabel="Delete"
        destructive
        busy={deleteBusyId === pendingDelete?.id}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return;
          void handleDeleteConversation(pendingDelete.id, pendingDelete.title);
        }}
      />

      <Modal
        open={!!renameTarget}
        onClose={() => (renameBusy ? null : setRenameTarget(null))}
        title="Rename conversation"
        maxWidthClassName="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label htmlFor="rename-title" className="text-sm font-semibold text-slate-600 dark:text-slate-200">
              Title
            </label>
            <input
              id="rename-title"
              type="text"
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              className="mt-2 w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900"
              placeholder="Untitled conversation"
              disabled={renameBusy}
            />
            <p className="mt-1 text-xs text-slate-400">Leave blank to remove the custom title.</p>
          </div>
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setRenameTarget(null)}
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-slate-700 dark:text-slate-200"
              disabled={renameBusy}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleRenameSave()}
              disabled={renameBusy}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:bg-slate-400 dark:bg-slate-100 dark:text-slate-900"
            >
              {renameBusy ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
