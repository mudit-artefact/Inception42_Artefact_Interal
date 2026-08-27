import { AlertTriangle, RotateCcw, ShieldCheck, X } from "lucide-react";
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
  onFeedback: (messageId: string, value: "up" | "down") => void;
}

export function ChatPanel({
  messages,
  status,
  error,
  onSend,
  onRetry,
  onDismissError,
  onFeedback,
}: ChatPanelProps) {
  const busy = status === "submitted";
  const isEmpty = messages.length === 0;

  const handleSubmit = (message: { text?: string }) => {
    const value = message.text ?? "";
    if (!value.trim() || busy) return;
    onSend(value);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Conversation className="min-h-0 flex-1">
        <ConversationContent className="mx-auto w-full max-w-3xl gap-6 px-4 py-6 sm:px-6">
          {isEmpty ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <InceptionLogo className="h-12 w-auto" height={48} />
              <div>
                <h2 className="font-display text-xl font-semibold text-foreground">
                  Ask about policies or your leave
                </h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
                  The HCS-01 concierge answers from approved HR and finance policy documents, and always shows
                  the clauses it used.
                </p>
              </div>
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
                <Shimmer className="text-sm">Checking the policy library…</Shimmer>
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
              placeholder="Ask about leave entitlement, notice periods, medical certificates…"
              disabled={busy}
              aria-label="Message the policy concierge"
            />
            <PromptInputFooter className="justify-between">
              <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <ShieldCheck aria-hidden="true" className="size-3.5 text-pink" />
                Answers cite official policy clauses
              </span>
              <PromptInputSubmit {...(busy ? { status: "submitted" as const } : {})} disabled={busy} />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  );
}
