import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Conversation } from "@/lib/api/types";

interface ConversationHistoryProps {
  conversations: Conversation[];
  activeId?: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClearAll?: () => void;
}

const formatDate = (iso: string) => {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay
    ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

export function ConversationHistory({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onClearAll,
}: ConversationHistoryProps) {
  // One empty, unused conversation is the cleared state, not something worth clearing.
  const hasAnythingToClear = conversations.some((c) => c.messages.length > 0);
  return (
    <nav aria-label="Conversation history" className="flex h-full min-h-0 flex-col">
      <div className="p-3">
        <Button onClick={onNew} className="w-full justify-start gap-2" size="sm">
          <Plus aria-hidden="true" className="size-4" />
          New conversation
        </Button>
      </div>
      <div className="flex items-center justify-between px-4 pb-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          History
        </p>
        {onClearAll && hasAnythingToClear ? (
          <button
            type="button"
            onClick={onClearAll}
            className="rounded text-[11px] text-muted-foreground underline-offset-2 transition-colors hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
          >
            Clear all
          </button>
        ) : null}
      </div>
      <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {conversations.map((c) => {
          const isActive = c.id === activeId;
          return (
            <li key={c.id} className="group relative">
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                aria-current={isActive ? "true" : undefined}
                className={`flex w-full items-start gap-2 rounded-md px-2 py-2 pr-8 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"
                }`}
              >
                <MessageSquare aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{c.title}</span>
                  <span className="text-muted-foreground">
                    {c.messages.length} message{c.messages.length === 1 ? "" : "s"} · {formatDate(c.updatedAt)}
                  </span>
                </span>
              </button>
              <button
                type="button"
                aria-label={`Delete conversation: ${c.title}`}
                onClick={() => onDelete(c.id)}
                className="absolute right-1 top-2 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
              >
                <Trash2 aria-hidden="true" className="size-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
