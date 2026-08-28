import { AlertTriangle, RotateCcw, ShieldCheck, Sparkles, X } from "lucide-react";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MessageFeedback } from "@/components/concierge/MessageFeedback";
import { SourceCitations } from "@/components/concierge/SourceCitations";
import { SuggestedQuestions } from "@/components/concierge/SuggestedQuestions";
import { SUGGESTED_QUESTIONS } from "@/lib/api/mock";
import type { ChatStatus } from "@/hooks/useConcierge";
import type { ChatMessage } from "@/lib/api/types";
import { InceptionLogo } from "@/components/common/InceptionLogo";

interface ChatPanelProps {
  messages: ChatMessage[];
  status: ChatStatus;
  error: string | null;
  onSend: (text: string) => void;
  onRetry: () => void;
  onDismissError: () => void;
  onFeedback: (id: string, value: "up" | "down") => void;
  isAwaitingClarification?: boolean;
}

export function ChatPanel({
  messages,
  status,
  error,
  onSend,
  onRetry,
  onDismissError,
  onFeedback,
  isAwaitingClarification = false,
}: ChatPanelProps) {
  const busy = status === "submitted";
  const isEmpty = messages.length === 0;

  const handleSubmit = (
    value: { text: string; files?: unknown[] },
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    const text = value.text.trim();
    if (!text || busy) return;
    onSend(text);
  };

  return (
    <div className="flex h-full flex-col">
      <Conversation className="flex-1">
        <ConversationContent className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 sm:px-6">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-pink/10 text-pink ring-8 ring-pink/5">
                <InceptionLogo className="h-8 w-auto" />
              </div>
              <h2 className="mt-4 font-display text-lg font-semibold tracking-tight text-foreground">
                How can I help with your HR policies today?
              </h2>
              <p className="mt-1.5 max-w-md text-xs text-muted-foreground">
                Ask about annual leave, carry-over caps, probation reviews, medical certificates, or line manager approvals.
              </p>
            </div>
          ) : null}

          {messages.map((m) => (
            <Message key={m.id} from={m.role}>
              {m.role === "assistant" ? (
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Concierge
                </p>
              ) : null}
              <MessageContent>
                <MessageResponse>{m.content}</MessageResponse>

                {/* Clarification Indicator for Ambiguous Queries */}
                {m.role === "assistant" && m.is_awaiting_clarification ? (
                  <div className="mt-3 flex items-center gap-2 pt-2 border-t border-amber-500/30">
                    <Badge variant="outline" className="gap-1 border-amber-500/40 bg-amber-500/10 text-amber-600 text-[10px]">
                      <AlertTriangle className="size-2.5" />
                      <span>Clarification Needed</span>
                    </Badge>
                    <span className="text-[10px] text-muted-foreground">
                      Please provide more details so I can give you an accurate answer.
                    </span>
                  </div>
                ) : null}

                {/* Proactive Greeting Action Pills */}
                {m.role === "assistant" && m.intent === "greeting" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/40">
                    <span className="text-[10px] text-muted-foreground font-medium mr-1">Quick Actions:</span>
                    <button
                      type="button"
                      onClick={() => onSend("How many annual leave days do I have left this year?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-pink/10 hover:bg-pink/20 text-pink font-medium transition-colors"
                    >
                      🌴 Check Leave Balance
                    </button>
                    <button
                      type="button"
                      onClick={() => onSend("What is the leave request workflow and notice period?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-muted hover:bg-muted/80 text-foreground font-medium transition-colors"
                    >
                      📄 Leave Request Workflow
                    </button>
                    <button
                      type="button"
                      onClick={() => onSend("Who is my current line manager and when did they change?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-muted hover:bg-muted/80 text-foreground font-medium transition-colors"
                    >
                      👔 Line Manager Info
                    </button>
                  </div>
                ) : null}

                {/* Query Intelligence Indicator */}
                {m.role === "assistant" && m.rewritten_query && m.intent !== "greeting" && m.intent !== "greeting_onboarding" && m.intent !== "not_in_scope" && m.intent !== "out_of_domain" && m.intent !== "ambiguous" ? (
                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                    <Badge variant="outline" className="gap-1 border-pink/20 bg-pink/5 text-[10px] text-pink">
                      <Sparkles className="size-2.5" />
                      <span>Query Intelligence</span>
                    </Badge>
                    <span className="font-mono bg-muted/60 px-1.5 py-0.5 rounded text-foreground/80">
                      Rewritten: "{m.rewritten_query.length > 55 ? `${m.rewritten_query.slice(0, 52)}…` : m.rewritten_query}"
                    </span>
                    {m.confidence_score ? (
                      <Badge variant="secondary" className="text-[10px] text-muted-foreground">
                        {Math.round(m.confidence_score * 100)}% Intent Match
                      </Badge>
                    ) : null}
                  </div>
                ) : null}
              </MessageContent>

              {m.role === "assistant" ? (
                <>
                  <SourceCitations sources={m.sources ?? []} />
                  <MessageFeedback
                    content={m.content}
                    feedback={m.feedback}
                    onFeedback={(value) => onFeedback(m.id, value)}
                  />
                </>
              ) : null}
            </Message>
          ))}

          {busy ? (
            <Message from="assistant">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Concierge
              </p>
              <MessageContent>
                <Shimmer className="text-sm">Analyzing policy library with hybrid retrieval…</Shimmer>
                <span className="flex gap-1 pt-1" aria-hidden="true">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-200ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-100ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60" />
                </span>
                <span className="sr-only" role="status">
                  The concierge is preparing an answer
                </span>
              </MessageContent>
            </Message>
          ) : null}

          {error ? (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
            >
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-destructive" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">Couldn't get an answer</p>
                <p className="mt-1 text-xs text-muted-foreground">{error}</p>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="outline" className="gap-1.5" onClick={onRetry}>
                    <RotateCcw aria-hidden="true" className="size-3.5" />
                    Try again
                  </Button>
                  <Button size="sm" variant="ghost" className="gap-1.5" onClick={onDismissError}>
                    <X aria-hidden="true" className="size-3.5" />
                    Dismiss
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      <div className="border-t bg-card/60 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl space-y-3 px-4 py-4 sm:px-6">
          {isEmpty ? (
            <SuggestedQuestions questions={SUGGESTED_QUESTIONS} onSelect={onSend} disabled={busy} />
          ) : null}
          <PromptInput onSubmit={handleSubmit}>
            <PromptInputTextarea
              placeholder={
                isAwaitingClarification
                  ? "Please provide more details to clarify your question…"
                  : "Ask about leave entitlement, notice periods, medical certificates…"
              }
              disabled={busy}
              aria-label="Message the policy concierge"
            />
            <PromptInputFooter className="justify-between">
              <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <ShieldCheck aria-hidden="true" className="size-3.5 text-pink" />
                Answers verified by Omni HR SQL & Official Policy PDFs
              </span>
              <PromptInputSubmit {...(busy ? { status: "submitted" as const } : {})} disabled={busy} />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}
