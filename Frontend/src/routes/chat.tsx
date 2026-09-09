import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";
import { ChatPanel } from "@/components/concierge/ChatPanel";
import { ConversationHistory } from "@/components/concierge/ConversationHistory";
import { AppShell, APP_TITLE } from "@/components/layout/AppShell";
import { useActiveEmployee } from "@/hooks/useActiveEmployee";
import { useConcierge } from "@/hooks/useConcierge";

const DESCRIPTION =
  "Ask HR policy and leave questions and get cited answers from the approved Dalīl policy library, with your live leave balance alongside.";

/**
 * The conversation. This was `/` until the dashboard took the front door; the page itself
 * is unchanged apart from the header and sidebar moving into `AppShell`.
 *
 * `q` carries a message typed somewhere else — the dashboard's chat bar, or an action card
 * naming a leave request. It is sent once on arrival and then cleared from the address, so
 * a refresh does not send it again. Nothing about who owns the chat's state changes: this
 * route still creates it, exactly as before.
 */
export const Route = createFileRoute("/chat")({
  validateSearch: (search: Record<string, unknown>): { q?: string } =>
    typeof search["q"] === "string" && search["q"].trim() ? { q: search["q"] } : {},
  head: () => ({
    meta: [
      { title: APP_TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: APP_TITLE },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: ConversationPage,
});

function ConversationPage() {
  const { employees, employeeId, selectEmployee, employee, settled } = useActiveEmployee();
  const concierge = useConcierge(employeeId);
  const { q } = Route.useSearch();
  const navigate = useNavigate();
  const alreadySent = useRef(false);

  // A question typed on the dashboard, delivered exactly once.
  //
  // Two things have to have settled before this can safely run, and both of them bit.
  //
  // `settled` — `employeeId` starts as a mock persona and is replaced when the directory
  // comes back from the network. The conversation store is keyed on it, so when it
  // changes the whole list is reloaded and anything written in the meantime is gone. That
  // only happens when the saved persona differs from the default, which is why the
  // message went missing some of the time and not others.
  //
  // `hydrated` — the store starts with a throwaway conversation and replaces the list
  // from localStorage in an effect of its own. Writing before that lands writes into the
  // conversation about to be discarded.
  //
  // After both, nothing re-keys and nothing reloads. `startNew` hands back the id it
  // made and `send` writes to that id by name, so there is no second render to wait for
  // and no way for the message to end up somewhere else. One effect, one guard, no race.
  const delivered = useRef(false);
  const { hydrated } = concierge;

  useEffect(() => {
    if (delivered.current || !q || !hydrated || !settled) return;
    delivered.current = true;
    const conversationId = concierge.startNew();
    void concierge.send(q, conversationId);
    // Out of the address, so a reload does not ask it again.
    void navigate({ to: "/chat", search: {}, replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, hydrated, settled]);

  return (
    <AppShell
      employees={employees}
      employeeId={employeeId}
      employee={employee}
      onSelectEmployee={selectEmployee}
      onNotificationAction={(prompt) => concierge.send(prompt)}
      secondaryPanel={
        <ConversationHistory
          conversations={concierge.conversations}
          activeId={concierge.activeId}
          onSelect={concierge.selectConversation}
          onNew={concierge.startNew}
          onDelete={concierge.deleteConversation}
          onClearAll={concierge.clearAll}
        />
      }
    >
      {/* Arriving from the dashboard, this is what replaces it. The dashboard shrinks
          away and the conversation comes up to meet it, so the two read as one movement
          rather than a page swap. */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="flex min-h-0 flex-1 flex-col bg-card"
      >
        <ChatPanel
          messages={concierge.active?.messages ?? []}
          status={concierge.status}
          stage={concierge.stage}
          error={concierge.error}
          onSend={concierge.send}
          onRetry={concierge.retry}
          onDismissError={concierge.dismissError}
          onFeedback={concierge.setFeedback}
          isAwaitingClarification={concierge.isAwaitingClarification}
          employeeId={employeeId}
        />
      </motion.div>
    </AppShell>
  );
}
