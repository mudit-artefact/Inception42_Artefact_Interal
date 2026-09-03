import { createFileRoute } from "@tanstack/react-router";
import { PanelLeft } from "lucide-react";
import { useState } from "react";
import { ChatPanel } from "@/components/concierge/ChatPanel";
import { ConversationHistory } from "@/components/concierge/ConversationHistory";
import { EmployeeCard } from "@/components/concierge/EmployeeCard";
import { NotificationCenter } from "@/components/concierge/NotificationCenter";
import { UserSwitcher } from "@/components/concierge/UserSwitcher";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useActiveEmployee } from "@/hooks/useActiveEmployee";
import { useConcierge } from "@/hooks/useConcierge";
import { InceptionLogo } from "@/components/common/InceptionLogo";

const TITLE = "Bayan HR";
const DESCRIPTION =
  "Ask HR policy and leave questions and get cited answers from the approved Bayan HR policy library, with your live leave balance alongside.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: TITLE },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: ConciergePage,
});

function ConciergePage() {
  const { employee, employees, employeeId, selectEmployee } = useActiveEmployee();
  const concierge = useConcierge(employeeId);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex shrink-0 items-center gap-3 border-b bg-card px-3 py-2.5 sm:px-4">
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="lg:hidden cursor-pointer" aria-label="Open menu">
              <PanelLeft aria-hidden="true" className="size-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[300px] p-0">
            <SheetTitle className="sr-only">Conversations and employee details</SheetTitle>
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b p-2">
                <UserSwitcher
                  employees={employees}
                  activeId={employeeId}
                  onSelect={selectEmployee}
                  className="w-full justify-start"
                />
              </div>
              <div className="min-h-0 flex-1 border-b">
                <ConversationHistory
                  conversations={concierge.conversations}
                  activeId={concierge.activeId}
                  onSelect={(id) => {
                    concierge.selectConversation(id);
                    setMobileNavOpen(false);
                  }}
                  onNew={() => {
                    concierge.startNew();
                    setMobileNavOpen(false);
                  }}
                  onDelete={concierge.deleteConversation}
                  onClearAll={() => {
                    concierge.clearAll();
                    setMobileNavOpen(false);
                  }}
                />
              </div>
              <div className="max-h-[55%] overflow-y-auto p-3">
                <EmployeeCard employee={employee} policyLinks={employee.policyLinks} />
              </div>
            </div>
          </SheetContent>
        </Sheet>

        {/* Desktop Sidebar Toggle Button */}
        <Button
          variant="ghost"
          size="icon-sm"
          className="hidden lg:inline-flex text-muted-foreground hover:text-foreground cursor-pointer"
          onClick={() => setSidebarOpen((prev) => !prev)}
          title={sidebarOpen ? "Close history sidebar" : "Open history sidebar"}
          aria-label={sidebarOpen ? "Close history sidebar" : "Open history sidebar"}
        >
          <PanelLeft aria-hidden="true" className="size-4" />
        </Button>

        <InceptionLogo className="h-7 w-auto shrink-0" />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-sm font-semibold tracking-tight">{TITLE}</h1>
        </div>

        <div className="flex items-center gap-2">
          <NotificationCenter
            employeeId={employeeId}
            onActionClick={(prompt) => concierge.sendMessage(prompt)}
          />
          <UserSwitcher employees={employees} activeId={employeeId} onSelect={selectEmployee} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {sidebarOpen && (
          <aside className="hidden w-[260px] shrink-0 border-r bg-sidebar lg:block">
            <ConversationHistory
              conversations={concierge.conversations}
              activeId={concierge.activeId}
              onSelect={concierge.selectConversation}
              onNew={concierge.startNew}
              onDelete={concierge.deleteConversation}
              onClearAll={concierge.clearAll}
            />
          </aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col bg-card">
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
          />
        </main>

        <aside className="hidden w-[300px] shrink-0 overflow-y-auto border-l bg-sidebar p-4 xl:block">
          <EmployeeCard employee={employee} policyLinks={employee.policyLinks} />
        </aside>
      </div>
    </div>
  );
}
