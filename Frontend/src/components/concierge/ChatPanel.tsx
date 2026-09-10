import { useState, useRef } from "react";
import {
  AlertTriangle,
  CalendarPlus,
  CheckCircle2,
  Clock,
  CornerDownLeft,
  FileSignature,
  FileText,
  GraduationCap,
  PlaneTakeoff,
  Paperclip,
  Plus,
  RotateCcw,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
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
import { DocumentUpload } from "@/components/concierge/DocumentUpload";
import { ContractSigning } from "@/components/concierge/ContractSigning";
import { VisaDocumentUpload } from "@/components/concierge/VisaDocumentUpload";
import { LeaveConfirmationCard } from "@/components/concierge/LeaveConfirmationCard";
import { LeaveCalendarPicker } from "@/components/concierge/LeaveCalendarPicker";
import { LeaveApprovedCard } from "@/components/concierge/LeaveApprovedCard";
import { ManagerApprovalCard } from "@/components/concierge/ManagerApprovalCard";
import { MessageFeedback } from "@/components/concierge/MessageFeedback";
import { SourceCitations } from "@/components/concierge/SourceCitations";
import { SuggestedQuestions } from "@/components/concierge/SuggestedQuestions";
import { AgenticCapabilities } from "@/components/concierge/AgenticCapabilities";
import { SUGGESTED_QUESTIONS } from "@/lib/api/mock";
import type { ChatStatus } from "@/hooks/useConcierge";
import type { ChatStage } from "@/lib/api/chat";
import type { ChatMessage } from "@/lib/api/types";

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

  // 1. Reconnect broken headings or dangling parentheses like "Annual Leave (\n26." -> "Annual Leave (2026)"
  formatted = formatted.replace(
    /([^\n(]+?)\s*\(\s*\n+(\d{2,4})\.?\)?/g,
    (_, heading, num) => {
      const cleanHeading = heading.trim();
      const year = num.length === 2 ? `20${num}` : num;
      return `${cleanHeading} (${year})\n`;
    }
  );
  // 2. Remove dangling open parenthesis at end of line
  formatted = formatted.replace(/\(\s*$/gm, "");

  // 3. Convert unicode bullet symbols (•, ●, ▪) into proper markdown list items (* )
  formatted = formatted.replace(/^[\u2022\u25CF\u25AA•●▪]\s*/gm, "* ");
  formatted = formatted.replace(/([:\.]\s*)[\u2022\u25CF\u25AA•●▪]\s*/g, "$1\n\n* ");
  formatted = formatted.replace(/(?<=[^\n])[^\S\n]+[\u2022\u25CF\u25AA•●▪]\s*/g, "\n* ");

  // 4. Ensure a blank line before any markdown bullet list that immediately follows a paragraph
  formatted = formatted.replace(/([^\n])\n(\*\s+|-\s+)/g, "$1\n\n$2");

  // 5. Ensure headings (### Heading) have clean line breaks before and after
  formatted = formatted.replace(/([^\n])\n(#{1,4}\s+)/g, "$1\n\n$2");

  // 6. Normalize excess blank lines (max 2 consecutive newlines)
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
  const [actionsOpen, setActionsOpen] = useState(false);
  // Which document panel is open, or null. It was a boolean when there was only the
  // school one; a second panel needs a name rather than another flag beside it.
  const [openPanel, setOpenPanel] = useState<
    "school-documents" | "visa-documents" | "contract" | null
  >(null);
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
      <Conversation className="flex-1 min-h-0">
        <ConversationContent className="mx-auto w-full max-w-5xl space-y-6 px-4 py-6 sm:px-8">
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center py-8 text-center animate-in fade-in-50 duration-500 max-w-4xl mx-auto w-full">
              <div className="space-y-1.5 mb-6">
                <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-display">
                  Hi, I'm Dalīl, your Everyday Agent!
                </h2>
                <p className="text-sm text-muted-foreground">
                  How can I help you today?
                </p>
              </div>

              {/* Middle: 4 Clean Agentic Capability Boxes */}
              <div className="w-full">
                <AgenticCapabilities
                  onSelectCapability={(prompt) => onSend(prompt)}
                  onOpenPanel={(panel) => setOpenPanel(panel)}
                  disabled={busy}
                />
              </div>
            </div>
          ) : null}

          {messages.map((m, i) => {
            let messageText = m.content;
            if (
              m.role === "assistant" &&
              m.action_payload?.action_type &&
              ["LEAVE_SUBMITTED_PENDING_APPROVAL", "LEAVE_SUBMITTED_SUCCESS"].includes(
                m.action_payload.action_type
              )
            ) {
              const lines = messageText.split("\n");
              const nonBulletLines = lines.filter((line) => {
                const trimmed = line.trim().toLowerCase();
                return (
                  !trimmed.startsWith("•") &&
                  !trimmed.startsWith("*") &&
                  !trimmed.startsWith("-") &&
                  !trimmed.includes("leave type:") &&
                  !trimmed.includes("current balance:") &&
                  !trimmed.includes("approver:") &&
                  !trimmed.includes("dates:") &&
                  !trimmed.includes("status:") &&
                  !trimmed.includes("calendar invite") &&
                  !trimmed.includes("forwarded to your line manager")
                );
              });
              messageText =
                nonBulletLines.join("\n").trim() ||
                "✅ Leave Request Submitted & Awaiting Manager Approval!";
            }

            return (
              <Message key={m.id} from={m.role}>
                <MessageContent>
                  <MessageResponse>{formatMessageContent(messageText)}</MessageResponse>

                {/* Clarification Indicator for Ambiguous Queries */}
                {m.role === "assistant" && m.is_awaiting_clarification && !m.action_payload ? (
                  <div className="mt-3 flex items-center gap-2 pt-2 border-t border-primary/20">
                    <Badge variant="outline" className="gap-1 border-primary/30 bg-primary/10 text-primary text-[10px]">
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
                    onSelectDates={(type, start, end, reason) => {
                      // The reason rides on the request itself. The step that reads a
                      // leave request already looks for one in the employee's words and
                      // has always found none here, because this sentence never carried
                      // it — the picker path guaranteed every request arrived reasonless.
                      onSend(
                        `I want to apply for ${type} from ${start} to ${end}` +
                          (reason ? `. The reason is: ${reason}` : ""),
                      );
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

                {/* Document Upload Action Button */}
                {/* The visa panel is chosen by action_type, like the leave cards. Only
                    the school button below is chosen by the intent label. */}
                {/* Signing, not sending — chosen by action_type like the visa panel beside it. */}
                      {m.action_payload?.action_type === "CONTRACT_SIGNING" ? (
                        <div className="mt-3 pt-2 border-t border-border/40">
                          <button
                            type="button"
                            onClick={() => setOpenPanel("contract")}
                            className="px-4 py-2.5 rounded-lg text-sm bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-colors flex items-center gap-2 cursor-pointer"
                          >
                            <FileSignature className="size-4" />
                            Sign Your Contract
                          </button>
                        </div>
                      ) : null}

                      {m.action_payload?.action_type === "VISA_DOCUMENT_UPLOAD" ? (
                  <div className="mt-3 pt-2 border-t border-border/40">
                    <button
                      type="button"
                      onClick={() => setOpenPanel("visa-documents")}
                      className="px-4 py-2.5 rounded-lg text-sm bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <UploadCloud className="size-4" />
                      Upload Visa Documents
                    </button>
                  </div>
                ) : null}

                {m.role === "assistant" && m.intent === "document_upload" ? (
                  <div className="mt-3 pt-2 border-t border-border/40">
                    <button
                      type="button"
                      onClick={() => setOpenPanel("school-documents")}
                      className="px-4 py-2.5 rounded-lg text-sm bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <UploadCloud className="size-4" />
                      Upload Documents
                    </button>
                  </div>
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
                  {!m.action_payload &&
                  !m.is_action_required &&
                  ![
                    "action_executed",
                    "action_confirmation",
                    "document_upload",
                    "greeting",
                    "not_in_scope",
                    "apply_leave",
                    "cancel_leave",
                    "check_leave_status",
                    "approve_leave",
                    "reject_leave",
                    "check_school_verification",
                    "submit_school_verification",
                    "review_school_cases",
                  ].includes(m.intent || "") ? (
                    <SourceCitations sources={m.sources ?? []} />
                  ) : null}
                  <MessageFeedback
                    content={m.content}
                    feedback={m.feedback}
                    onFeedback={(value) => onFeedback(m.id, value)}
                  />
                </>
              ) : null}
            </Message>
          );
        })}

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

      <div className="border-t bg-card/80 backdrop-blur-md px-4 py-3 shrink-0 sm:px-8">
        <div className="mx-auto w-full max-w-5xl">
          {/* FAQs just above chatbot input */}
          {isEmpty && (
            <div className="mb-3">
              <SuggestedQuestions
                onSelect={(q) => onSend(q)}
                disabled={busy}
              />
            </div>
          )}

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
            <Popover open={actionsOpen} onOpenChange={setActionsOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    "flex size-8.5 shrink-0 items-center justify-center rounded-full transition-all duration-200 cursor-pointer shadow-2xs hover:scale-105 active:scale-95 border",
                    actionsOpen
                      ? "bg-primary text-primary-foreground border-primary rotate-45"
                      : "bg-muted/70 text-foreground hover:bg-primary/15 hover:text-primary border-border/60"
                  )}
                  title="Quick Actions (+)"
                  aria-label="Quick Actions"
                >
                  <Plus className="size-4.5 stroke-[2.5]" />
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                side="top"
                sideOffset={14}
                className="w-80 p-2 shadow-2xl border border-border bg-card text-card-foreground rounded-2xl z-50 animate-in fade-in-50 zoom-in-95"
              >
                <div className="px-2 py-1.5 mb-1 border-b border-border/50">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Quick Actions
                  </span>
                </div>
                <div className="space-y-1">
                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      onSend("I want to apply for leave");
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-primary/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-primary/15 text-primary mt-0.5 group-hover:scale-105 transition-transform">
                      <CalendarPlus className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">Submit Leave Request</div>
                      <div className="text-[10px] text-muted-foreground">Apply for annual, sick, or remote work</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      setOpenPanel("contract");
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-primary/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-primary/15 text-primary mt-0.5 group-hover:scale-105 transition-transform">
                      <FileSignature className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">
                        Sign Your Contract
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        Read and sign your employment contract
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      setOpenPanel("visa-documents");
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-amber-500/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400 mt-0.5 group-hover:scale-105 transition-transform">
                      <PlaneTakeoff className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">
                        Upload Visa Documents
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        Send your employment visa joining documents
                      </div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      setOpenPanel("school-documents");
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-pink-500/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-pink-500/15 text-pink-600 dark:text-pink-400 mt-0.5 group-hover:scale-105 transition-transform">
                      <GraduationCap className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">Upload School Documents</div>
                      <div className="text-[10px] text-muted-foreground">Submit HCS-11 school verification documents</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      fileInputRef.current?.click();
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-amber-500/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400 mt-0.5 group-hover:scale-105 transition-transform">
                      <UploadCloud className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">Upload a File</div>
                      <div className="text-[10px] text-muted-foreground">Attach medical certificates or verification documents</div>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setActionsOpen(false);
                      onSend("What leave requests do I need to approve?");
                    }}
                    className="w-full flex items-start gap-2.5 p-2 rounded-xl text-left cursor-pointer hover:bg-blue-500/10 transition-colors group"
                  >
                    <div className="p-1.5 rounded-lg bg-blue-500/15 text-blue-600 dark:text-blue-400 mt-0.5 group-hover:scale-105 transition-transform">
                      <CheckCircle2 className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-foreground">Approve Leave Requests</div>
                      <div className="text-[10px] text-muted-foreground">Review pending team approvals as manager</div>
                    </div>
                  </button>
                </div>
              </PopoverContent>
            </Popover>

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

      {/* Document Upload Modal */}
      {openPanel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          {openPanel === "contract" ? (
            <ContractSigning employeeId={employeeId} onClose={() => setOpenPanel(null)} />
          ) : openPanel === "visa-documents" ? (
            <VisaDocumentUpload employeeId={employeeId} onClose={() => setOpenPanel(null)} />
          ) : (
            <DocumentUpload employeeId={employeeId} onClose={() => setOpenPanel(null)} />
          )}
        </div>
      )}
    </div>
  );
}


