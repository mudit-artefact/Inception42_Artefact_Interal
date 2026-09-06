import { useState, useRef } from "react";
import {
  AlertTriangle,
  BarChart2,
  CalendarPlus,
  CheckCircle2,
  Clock,
  CornerDownLeft,
  FileText,
  Paperclip,
  Plus,
  RotateCcw,
  Sparkles,
  UploadCloud,
  UserCheck,
  X,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataChart } from "@/components/concierge/DataChart";
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
  employeeId?: string;
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
  employeeId = "EMP001",
}: ChatPanelProps) {
  const busy = status === "submitted" && stage !== null;
  const isEmpty = messages.length === 0;
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (
    value: { text: string; files?: unknown[] },
    event: React.FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    const text = value.text.trim();
    if ((!text && !attachedFile) || busy) return;
    const finalMessage = attachedFile
      ? `[Uploaded document: ${attachedFile.name}] ${text || "I have uploaded this document."}`
      : text;
    onSend(finalMessage);
    setAttachedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <Conversation className="flex-1 min-h-0 overflow-y-auto">
        <ConversationContent className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 sm:px-6">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center py-10 text-center animate-in fade-in-50 duration-500">
              <div className="mb-4 flex items-center justify-center">
                <InceptionLogo className="h-10 sm:h-12 w-auto" />
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-display">
                What can I help with?
              </h2>
              <p className="mt-2 max-w-md text-xs sm:text-sm text-muted-foreground">
                Ask about company HR policies, submit leave applications, review team approvals, or check your live balances.
              </p>

              {/* Action shortcuts matching prompt style */}
              <div className="mt-8 grid w-full max-w-lg gap-2 text-left">
                <button
                  type="button"
                  onClick={() => onSend("I want to apply for leave")}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/70 bg-card/50 hover:bg-accent/70 hover:border-primary/40 text-foreground transition-all duration-200 group cursor-pointer shadow-xs"
                >
                  <div className="p-2 rounded-lg bg-primary/10 text-primary group-hover:scale-105 transition-transform">
                    <CalendarPlus className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold">Submit a leave request</div>
                    <div className="text-[11px] text-muted-foreground">Apply for annual, sick, or remote work</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSend("What leave requests do I need to approve?")}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/70 bg-card/50 hover:bg-accent/70 hover:border-blue-500/40 text-foreground transition-all duration-200 group cursor-pointer shadow-xs"
                >
                  <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 group-hover:scale-105 transition-transform">
                    <CheckCircle2 className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold">Approve leave requests (Manager)</div>
                    <div className="text-[11px] text-muted-foreground">Review and decide on pending team submissions</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSend("How many annual leave days do I have left this year?")}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/70 bg-card/50 hover:bg-accent/70 hover:border-pink/40 text-foreground transition-all duration-200 group cursor-pointer shadow-xs"
                >
                  <div className="p-2 rounded-lg bg-pink/10 text-pink group-hover:scale-105 transition-transform">
                    <BarChart2 className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold">Check my leave balances & status</div>
                    <div className="text-[11px] text-muted-foreground">Deterministic lookup from your live Omni HR record</div>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => onSend("What is the sick leave policy with pay entitlement?")}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/70 bg-card/50 hover:bg-accent/70 hover:border-amber-500/40 text-foreground transition-all duration-200 group cursor-pointer shadow-xs"
                >
                  <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 group-hover:scale-105 transition-transform">
                    <FileText className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold">Search HR policies & rules</div>
                    <div className="text-[11px] text-muted-foreground">Citations grounded in official HC Services documentation</div>
                  </div>
                </button>
              </div>
            </div>
          ) : null}

          {messages.map((m, i) => (
            <Message key={m.id} from={m.role}>
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

                {/* Chart visualization for numeric data */}
                {m.role === "assistant" && m.chart ? (
                  <DataChart chart={m.chart} />
                ) : null}

                {/* Proactive Greeting Action Pills */}
                {m.role === "assistant" && m.intent === "greeting" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/40">
                    <span className="text-[10px] text-muted-foreground font-medium mr-1">Quick Actions:</span>
                    <button
                      type="button"
                      onClick={() => onSend("How many annual leave days do I have left this year?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-pink/10 hover:bg-pink/20 text-pink font-medium transition-colors cursor-pointer"
                    >
                      🌴 Check Leave Balance
                    </button>
                    <button
                      type="button"
                      onClick={() => onSend("Who is my current line manager and when did they change?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-muted hover:bg-muted/80 text-foreground font-medium transition-colors cursor-pointer"
                    >
                      👔 Line Manager Info
                    </button>
                    <button
                      type="button"
                      onClick={() => onSend("I want to apply for leave")}
                      className="px-2 py-1 rounded-md text-[11px] bg-primary/10 hover:bg-primary/20 text-primary font-medium transition-colors cursor-pointer"
                    >
                      🌴 Do you want to apply for leave?
                    </button>
                    <button
                      type="button"
                      onClick={() => onSend("How do I submit school document verification for my children?")}
                      className="px-2 py-1 rounded-md text-[11px] bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 font-medium transition-colors cursor-pointer"
                    >
                      🏫 School Document Verification
                    </button>
                  </div>
                ) : null}

                {/* Proactive Leave Application Suggestion Pill (for non-greeting messages) */}
                {m.role === "assistant" &&
                m.intent !== "greeting" &&
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

                {/* Calendar Date-Range Picker */}
                {m.action_payload?.action_type === "SHOW_LEAVE_CALENDAR_PICKER" ? (
                  <LeaveCalendarPicker
                    leaveType={m.action_payload.leave_type}
                    minDate={m.action_payload.min_date}
                    onSelectDates={(type, start, end) => {
                      onSend(`I want to apply for ${type} from ${start} to ${end}`);
                    }}
                  />
                ) : null}

                {/* Manager Approvals Card */}
                {m.action_payload?.action_type === "MANAGER_PENDING_APPROVALS" &&
                m.action_payload.pending_approvals ? (
                  <ManagerApprovalCard
                    pendingApprovals={m.action_payload.pending_approvals}
                    onAction={onSend}
                  />
                ) : null}

                {/* Post-Approval Celebration & Calendar/Email Card */}
                {m.action_payload?.action_type === "LEAVE_APPROVED_NOTIFICATION" &&
                m.action_payload.approved_leave ? (
                  <LeaveApprovedCard approvedLeave={m.action_payload.approved_leave} />
                ) : null}

                {/* Agentic Leave Confirmation & Receipt Cards */}
                {m.action_payload &&
                m.action_payload.action_type &&
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
              <MessageContent>
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
                  {stage?.text ?? "Preparing an answer…"}
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

      <div className="border-t bg-card/80 backdrop-blur-md px-4 py-3 shrink-0">
        <div className="mx-auto w-full max-w-4xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const inputEl = e.currentTarget.elements.namedItem("message") as HTMLInputElement;
              const text = (inputEl?.value || "").trim();
              if ((!text && !attachedFile) || busy) return;
              const finalMessage = attachedFile
                ? `[Uploaded document: ${attachedFile.name}] ${text || "I have uploaded this document."}`
                : text;
              onSend(finalMessage);
              if (inputEl) inputEl.value = "";
              setAttachedFile(null);
              if (fileInputRef.current) fileInputRef.current.value = "";
            }}
            className="relative flex items-center gap-2 rounded-full border border-border/80 bg-background px-3 py-1.5 shadow-md transition-all focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/20"
          >
            {/* Hidden File Input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setAttachedFile(file);
                }
              }}
            />

            {/* The Plus (+) Button on the Left */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex size-8.5 shrink-0 items-center justify-center rounded-full bg-muted/70 text-foreground hover:bg-primary/15 hover:text-primary transition-all duration-200 cursor-pointer shadow-2xs hover:scale-105 active:scale-95 border border-border/60"
                  title="Quick Actions (+)"
                  aria-label="Quick Actions"
                >
                  <Plus className="size-4.5 stroke-[2.5]" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                side="top"
                sideOffset={12}
                className="w-80 p-1.5 shadow-2xl border-border/80 bg-popover/95 backdrop-blur-md rounded-2xl animate-in fade-in-50 zoom-in-95 z-50"
              >
                <DropdownMenuItem
                  onClick={() => onSend("I want to apply for leave")}
                  className="flex items-start gap-2.5 p-2 rounded-xl cursor-pointer hover:bg-primary/10 transition-colors"
                >
                  <div className="p-1.5 rounded-lg bg-primary/15 text-primary mt-0.5">
                    <CalendarPlus className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-foreground">Submit Leave Request</div>
                    <div className="text-[10px] text-muted-foreground">Apply for annual, sick, or remote work</div>
                  </div>
                </DropdownMenuItem>

                <DropdownMenuItem
                  onClick={() => onSend("What leave requests do I need to approve?")}
                  className="flex items-start gap-2.5 p-2 rounded-xl cursor-pointer hover:bg-blue-500/10 transition-colors"
                >
                  <div className="p-1.5 rounded-lg bg-blue-500/15 text-blue-600 dark:text-blue-400 mt-0.5">
                    <CheckCircle2 className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-foreground">Approve Leave Requests</div>
                    <div className="text-[10px] text-muted-foreground">Review pending team approvals as manager</div>
                  </div>
                </DropdownMenuItem>

                <DropdownMenuItem
                  onClick={() => onSend("Requested leaves? (Does my leaves approved by my manager)")}
                  className="flex items-start gap-2.5 p-2 rounded-xl cursor-pointer hover:bg-emerald-500/10 transition-colors"
                >
                  <div className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 mt-0.5">
                    <Clock className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-foreground">My Leave Request Status</div>
                    <div className="text-[10px] text-muted-foreground">Check manager approval status on your requests</div>
                  </div>
                </DropdownMenuItem>

                <DropdownMenuItem
                  onClick={() => fileInputRef.current?.click()}
                  className="flex items-start gap-2.5 p-2 rounded-xl cursor-pointer hover:bg-amber-500/10 transition-colors"
                >
                  <div className="p-1.5 rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400 mt-0.5">
                    <UploadCloud className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-foreground">Upload a File</div>
                    <div className="text-[10px] text-muted-foreground">Attach medical certificates or verification documents</div>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Attached File Chip (if file is selected) */}
            {attachedFile ? (
              <div className="flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-xs text-primary max-w-[180px] truncate animate-in fade-in-50">
                <Paperclip className="size-3 shrink-0" />
                <span className="truncate">{attachedFile.name}</span>
                <button
                  type="button"
                  onClick={() => {
                    setAttachedFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  className="ml-1 rounded-full hover:bg-primary/20 p-0.5 text-primary/70 hover:text-primary cursor-pointer"
                  aria-label="Remove attachment"
                >
                  <X className="size-2.5" />
                </button>
              </div>
            ) : null}

            {/* Center: The Text Input Field */}
            <input
              name="message"
              type="text"
              autoComplete="off"
              placeholder={
                attachedFile
                  ? "Add a note with your file (optional)…"
                  : isAwaitingClarification
                  ? "Please provide more details to clarify your question…"
                  : "Ask anything about leave policies, submit requests, check balances…"
              }
              disabled={busy}
              aria-label="Message Dalīl"
              className="flex-1 bg-transparent px-2 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
            />

            {/* Right: Submit / Send Button */}
            <button
              type="submit"
              disabled={busy}
              aria-label="Send message"
              className={cn(
                "flex size-8.5 shrink-0 items-center justify-center rounded-full transition-all duration-200 shadow-xs cursor-pointer",
                busy
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90 hover:scale-105 active:scale-95"
              )}
            >
              {busy ? (
                <span className="size-4 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
              ) : (
                <CornerDownLeft className="size-4 stroke-[2.5]" />
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}


