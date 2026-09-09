import { useNavigate } from "@tanstack/react-router";
import { ArrowUp, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";

/**
 * Start a conversation from the dashboard.
 *
 * On enter the page hands the message to `/chat`, which sends it on arrival. The dashboard
 * fades and lifts away first — `leaving` drives that, and the navigation waits for it —
 * so the answer opens on a screen that has visibly become the conversation rather than
 * replacing it in a single frame.
 *
 * The chat's own state is untouched by this: `/chat` still creates it, exactly as it did
 * when it was the front door.
 */
export function NewChatBox({ onLeaving }: { onLeaving: () => void }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const navigate = useNavigate();

  const start = (event: FormEvent) => {
    event.preventDefault();
    const question = text.trim();
    if (!question || sending) return;

    setSending(true);
    onLeaving();
    // No `viewTransition` here. The browser's own crossfade ran on top of the fade below
    // and the two fought: the dashboard was captured mid-fade as the outgoing snapshot,
    // so it flashed back in at partial opacity before disappearing. One animation, owned
    // by one place, is the whole fix.
    window.setTimeout(() => {
      void navigate({ to: "/chat", search: { q: question } });
    }, 200);
  };

  return (
    <form
      onSubmit={start}
      className="flex items-center gap-3 rounded-2xl border bg-card p-3 shadow-sm"
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
        <Sparkles className="size-4.5 text-primary" aria-hidden="true" />
      </div>
      <input
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={sending}
        placeholder="Start a new chat with Dalīl…"
        aria-label="Start a new chat"
        className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-60"
      />
      <Button
        type="submit"
        size="icon"
        disabled={!text.trim() || sending}
        className="size-10 shrink-0 rounded-full"
        aria-label="Send"
      >
        <ArrowUp className="size-4" aria-hidden="true" />
      </Button>
    </form>
  );
}
