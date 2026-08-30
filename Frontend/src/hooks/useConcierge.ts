import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { sendChatMessage } from "@/lib/api/chat";
import type { ChatMessage, Conversation } from "@/lib/api/types";

// Chat history lives in the browser, one entry per employee. Nothing on the server can
// reach it, so resetting the backend leaves every old conversation on screen — which is
// exactly as confusing as it sounds.
//
// The version in the key is how that gets fixed without asking anyone to open a console.
// Raising it orphans every conversation stored under the previous version, and the sweep
// below deletes them on the next load. Raise it only for a deliberate clean slate.
const STORAGE_VERSION = "v2";
const KEY_PREFIX = "hcs01.conversations";
const storageKey = (employeeId: string) => `${KEY_PREFIX}.${STORAGE_VERSION}.${employeeId}`;

function forgetEarlierVersions() {
  if (typeof window === "undefined") return;
  try {
    const current = `${KEY_PREFIX}.${STORAGE_VERSION}.`;
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith(KEY_PREFIX) && !key.startsWith(current))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch {
    /* private mode, or storage disabled — nothing stored means nothing to sweep */
  }
}

export type ChatStatus = "ready" | "submitted" | "error" | "awaiting_clarification";

const uid = () => Math.random().toString(36).slice(2, 10);

const newConversation = (): Conversation => ({
  id: `local-${uid()}`,
  remoteId: null,
  title: "New conversation",
  updatedAt: new Date().toISOString(),
  messages: [],
});

function load(key: string): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? (JSON.parse(raw) as Conversation[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useConcierge(employeeId: string) {
  const key = storageKey(employeeId);
  const [hydrated, setHydrated] = useState(false);
  const loadedKey = useRef<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([newConversation()]);
  const [activeId, setActiveId] = useState<string>(() => "");
  const [status, setStatus] = useState<ChatStatus>("ready");
  const [error, setError] = useState<string | null>(null);
  const lastMessage = useRef<string | null>(null);
  // Track pending clarification state
  const pendingClarification = useRef<{ originalQuestion: string } | null>(null);

  useEffect(() => {
    forgetEarlierVersions();
    const stored = load(key);
    setStatus("ready");
    setError(null);
    if (stored.length > 0) {
      setConversations(stored);
      setActiveId(stored[0]!.id);
    } else {
      const fresh = newConversation();
      setConversations([fresh]);
      setActiveId(fresh.id);
    }
    loadedKey.current = key;
    setHydrated(true);
  }, [key]);

  useEffect(() => {
    if (!hydrated || loadedKey.current !== key) return;
    try {
      window.localStorage.setItem(key, JSON.stringify(conversations));
    } catch {
      /* quota or private mode – history stays in memory */
    }
  }, [conversations, hydrated, key]);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? conversations[0]!,
    [conversations, activeId],
  );

  const patchActive = useCallback(
    (updater: (c: Conversation) => Conversation) => {
      setConversations((prev) => prev.map((c) => (c.id === active?.id ? updater(c) : c)));
    },
    [active?.id],
  );

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || status === "submitted") return;
      lastMessage.current = message;
      setError(null);
      setStatus("submitted");

      const userMessage: ChatMessage = {
        id: uid(),
        role: "user",
        content: message,
        createdAt: new Date().toISOString(),
      };

      patchActive((c) => ({
        ...c,
        title: c.messages.length === 0 ? message.slice(0, 60) : c.title,
        updatedAt: userMessage.createdAt,
        messages: [...c.messages, userMessage],
      }));

      try {
        // Check if this is a clarification response
        const clarificationData = pendingClarification.current;

        const res = await sendChatMessage(message, active?.remoteId ?? null, {
          employeeId,
          // Pass clarification context if pending
          originalQuestion: clarificationData?.originalQuestion ?? null,
          userClarification: clarificationData ? message : null,
        });

        // Clear pending clarification after sending
        pendingClarification.current = null;

        const assistant: ChatMessage = {
          id: uid(),
          role: "assistant",
          content: res.answer,
          createdAt: new Date().toISOString(),
          sources: res.sources,
          feedback: null,
          intent: res.intent,
          rewritten_query: res.rewritten_query,
          confidence_score: res.confidence_score,
          is_awaiting_clarification: res.is_awaiting_clarification,
          original_question: res.original_question,
        };

        patchActive((c) => ({
          ...c,
          remoteId: res.conversation_id || c.remoteId,
          updatedAt: assistant.createdAt,
          messages: [...c.messages, assistant],
        }));

        // Check if awaiting clarification
        if (res.is_awaiting_clarification && res.original_question) {
          pendingClarification.current = { originalQuestion: res.original_question };
          setStatus("awaiting_clarification");
        } else {
          setStatus("ready");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
        setStatus("error");
      }
    },
    [active?.id, active?.remoteId, employeeId, patchActive, status],
  );

  const retry = useCallback(() => {
    const text = lastMessage.current;
    if (!text) return;
    // drop the failed user turn before resending
    patchActive((c) => ({
      ...c,
      messages: c.messages.filter(
        (m, i) => !(i === c.messages.length - 1 && m.role === "user" && m.content === text),
      ),
    }));
    setStatus("ready");
    setError(null);
    void send(text);
  }, [patchActive, send]);

  const setFeedback = useCallback(
    (messageId: string, feedback: "up" | "down") => {
      patchActive((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.id === messageId ? { ...m, feedback: m.feedback === feedback ? null : feedback } : m,
        ),
      }));
    },
    [patchActive],
  );

  const startNew = useCallback(() => {
    const conversation = newConversation();
    setConversations((prev) => [conversation, ...prev.filter((c) => c.messages.length > 0)]);
    setActiveId(conversation.id);
    setStatus("ready");
    setError(null);
  }, []);

  // "New conversation" adds one above the others, which is right for starting a thread
  // and no use at all for clearing the list. This is the other thing people mean when
  // they say they want to start fresh.
  const clearAll = useCallback(() => {
    const conversation = newConversation();
    setConversations([conversation]);
    setActiveId(conversation.id);
    setStatus("ready");
    setError(null);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        const list = next.length > 0 ? next : [newConversation()];
        setActiveId((current) => (current === id ? list[0]!.id : current));
        return list;
      });
    },
    [],
  );

  return {
    hydrated,
    conversations,
    active,
    activeId: active?.id,
    status,
    error,
    send,
    retry,
    setFeedback,
    startNew,
    selectConversation: setActiveId,
    deleteConversation,
    clearAll,
    dismissError: () => {
      setError(null);
      setStatus("ready");
    },
    // Clarification helpers
    isAwaitingClarification: status === "awaiting_clarification",
    cancelClarification: () => {
      pendingClarification.current = null;
      setStatus("ready");
    },
  };
}
