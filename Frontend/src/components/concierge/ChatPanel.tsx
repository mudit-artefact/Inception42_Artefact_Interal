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
import { LeaveConfirmationCard } from "@/components/concierge/LeaveConfirmationCard";
import { LeaveCalendarPicker } from "@/components/concierge/LeaveCalendarPicker";
import { LeaveApprovedCard } from "@/components/concierge/LeaveApprovedCard";
import { ManagerApprovalCard } from "@/components/concierge/ManagerApprovalCard";
import { MessageFeedback } from "@/components/concierge/MessageFeedback";


import { SourceCitations } from "@/components/concierge/SourceCitations";
import { SuggestedQuestions } from "@/components/concierge/SuggestedQuestions";
import { SUGGESTED_QUESTIONS } from "@/lib/api/mock";
import type { ChatStatus } from "@/hooks/useConcierge";
import type { ChatStage } from "@/lib/api/chat";
import type { ChatMessage } from "@/lib/api/types";
import { InceptionLogo } from "@/components/common/InceptionLogo";

interface ChatPanelProps {
  stage?: ChatStage | null;
  messages: ChatMessage[];
  status: ChatStatus;
  error: string | null;
  onSend: (text: string) => void;
  onRetry: () => void;
  onDismissError: () => void;
  onFeedback: (id: string, value: "up" | "down") => void;
  isAwaitingClarification?: boolean;
}

function formatMessageContent(content: string): string {
  if (!content) return "";
  let formatted = content;

  // 1. Convert inline or unicode bullet symbols (•, ●, ▪) into proper multi-line Markdown lists (* )
  formatted = formatted.replace(/([:\.]\s*)[•●▪]\s*/g, "$1\n\n* ");
  formatted = formatted.replace(/(?<!\n)\s*[•●▪]\s*/g, "\n* ");
  formatted = formatted.replace(/^[•●▪]\s*/gm, "* ");

  // 2. Convert inline numbered lists (e.g. "... text: 1. Item 2. Item 3. Item") into multi-line numbered lists
  formatted = formatted.replace(/([:\.]\s*)(1[\.\)]\s+)/g, "$1\n\n$2");
  formatted = formatted.replace(/(?<!\n)\s*(\d+[\.\)]\s+)/g, "\n$1");

  // 3. Ensure a blank line before any list that starts right after a paragraph
  formatted = formatted.replace(/([^\n])\n(\d+[\.\)]\s+|\*\s+|-\s+)/g, "$1\n\n$2");

  // 4. Normalize excess blank lines
  formatted = formatted.replace(/\n{3,}/g, "\n\n");
  return formatted.trim();
}

export function ChatPanel({
  messages,
  status,
  stage,
  error,
  onSend,
  onRetry,
  onDismissError,
  onFeedback,
  isAwaitingClarification = false,
}: ChatPanelProps) {
  const busy = status === "submitted" && stage !== null;
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

          {messages.map((m, i) => (
            <Message key={m.id} from={m.role}>

              {m.role === "assistant" ? (
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Concierge
                </p>
              ) : null}
              <MessageContent>
                <MessageResponse>{formatMessageContent(m.content)}</MessageResponse>

                {/* Clarification Indicator for Ambiguous Queries */}
                {m.role === "assistant" && m.is_awaiting_clarification && !m.action_payload ? (
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

                {/* Proactive Leave Application Suggestion Pill (Req #2) */}
                {m.role === "assistant" &&
                i === messages.length - 1 &&
                !m.action_payload &&
                (m.content.toLowerCase().includes("leave") ||
                  m.content.toLowerCase().includes("balance") ||
                  m.content.toLowerCase().includes("vacation") ||
                  m.content.toLowerCase().includes("إجازة")) ? (
                  <div className="mt-2.5 flex items-center">
                    <button
                      type="button"
                      onClick={() => onSend("I want to apply for leave")}
                      className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary transition-all hover:bg-primary/20 hover:scale-[1.02] shadow-2xs cursor-pointer"
                    >
                      <span>🌴</span>
                      <span>Do you want to apply for leave?</span>
                    </button>
                  </div>
                ) : null}

                {/* Calendar Date-Range Picker (Req #4) */}
                {m.action_payload?.action_type === "SHOW_LEAVE_CALENDAR_PICKER" ? (
                  <LeaveCalendarPicker
                    leaveType={m.action_payload.leave_type}
                    minDate={m.action_payload.min_date}
                    onSelectDates={(type, start, end) => {
                      onSend(`I want to apply for ${type} from ${start} to ${end}`);
                    }}
                  />
                ) : null}

                {/* Manager Approvals Card (Req #3) */}
                {m.action_payload?.action_type === "MANAGER_PENDING_APPROVALS" &&
                m.action_payload.pending_approvals ? (
                  <ManagerApprovalCard
                    pendingApprovals={m.action_payload.pending_approvals}
                    onAction={onSend}
                  />
                ) : null}

                {/* Post-Approval Celebration & Calendar/Email Card (Req #5 & #1) */}
                {m.action_payload?.action_type === "LEAVE_APPROVED_NOTIFICATION" &&
                m.action_payload.approved_leave ? (
                  <LeaveApprovedCard approvedLeave={m.action_payload.approved_leave} />
                ) : null}

                {/* Agentic Leave Confirmation & Receipt Cards (Req #1) */}
                {m.action_payload &&
                [
                  "CONFIRM_LEAVE_APPLICATION",
                  "LEAVE_SUBMITTED_PENDING_APPROVAL",
                  "LEAVE_SUBMITTED_SUCCESS",
                  "POLICY_VIOLATION",
                ].includes(m.action_payload.action_type) ? (
                  <LeaveConfirmationCard
                    payload={m.action_payload}
                    onConfirm={onSend}
                    isLatestAssistantMessage={i === messages.length - 1}
                  />
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
                {/* The live step, replaced as the workflow advances. It used to be one
                    fixed sentence for the whole wait, which said the same thing whether
                    the answer took four seconds or sixty. */}
                <Shimmer className="text-sm">
                  {stage?.text ?? "Working on it…"}
                </Shimmer>
                {stage?.found?.length ? (
                  <ul className="mt-1.5 space-y-0.5">
                    {stage.found.map((clause) => (
                      <li key={clause} className="text-xs text-muted-foreground">
                        <span className="text-primary">✦</span> {clause.replace(/§\s*/g, "Section ").replace(/§/g, "Section ")}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <span className="flex gap-1 pt-1" aria-hidden="true">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-200ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-100ms]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60" />
                </span>
                <span className="sr-only" role="status">
                  {stage?.text ?? "The concierge is preparing an answer"}
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
