import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Conversation } from "@/lib/api/types";

interface ConversationHistoryProps {
  conversations: Conversation[];
  activeId?: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
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
}: ConversationHistoryProps) {
  return (
    <nav aria-label="Conversation history" className="flex h-full min-h-0 flex-col">
      <div className="p-3">
        <Button onClick={onNew} className="w-full justify-start gap-2" size="sm">
          <Plus aria-hidden="true" className="size-4" />
          New conversation
        </Button>
      </div>
      <p className="px-4 pb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        History
      </p>
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
