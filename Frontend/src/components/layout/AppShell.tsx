import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Home, MessageSquare, PanelLeft, Route as RouteIcon } from "lucide-react";
import { useState, type ReactNode } from "react";
import { InceptionLogo } from "@/components/common/InceptionLogo";
import { NotificationCenter } from "@/components/concierge/NotificationCenter";
import { UserSwitcher } from "@/components/concierge/UserSwitcher";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import type { EmployeeProfile } from "@/lib/api/types";

export const APP_TITLE = "Dalīl";

/**
 * Only routes that exist and show something the others do not.
 *
 * The design also had My tasks and My documents. Neither has anything behind it — no
 * table, no endpoint, no service — and a navigation item that opens an empty page is a
 * promise the product has not made yet.
 *
 * There was a My requests page too, briefly. It listed exactly what the dashboard already
 * lists: the busiest person in the system has six requests, and the only thing the second
 * page added was the sixth, because the dashboard was truncating at five. The cap was the
 * problem, so the cap went and the page went with it.
 */
const NAV = [
  { to: "/", label: "Home", icon: Home, joinersOnly: false },
  { to: "/chat", label: "Conversations", icon: MessageSquare, joinersOnly: false },
  // The one item that is not for everybody. It is a real page over real data — which is
  // the test the two rejected above failed — but it describes a journey that is over for
  // most people, and a link to somebody else's journey is worse than no link.
  { to: "/onboarding", label: "My Onboarding", icon: RouteIcon, joinersOnly: true },
] as const;

interface AppShellProps {
  employees: EmployeeProfile[];
  employeeId: string;
  employee: EmployeeProfile | null;
  onSelectEmployee: (id: string) => void;
  /**
   * The signed-in person's job title, where the page knows one better than the record —
   * a new joiner's is stated on the contract they are being asked to sign, and it differs
   * from the one seeded here for every one of them.
   */
  activeJobTitle?: string | null | undefined;
  /** Where a notification's action button sends the person. */
  onNotificationAction?: (prompt: string) => void;
  /**
   * A second column belonging to the page rather than the app — the chat's conversation
   * list. It sits below the navigation so both are reachable without the page having to
   * rebuild the header to get one.
   */
  secondaryPanel?: ReactNode;
  children: ReactNode;
}

export function AppShell({
  employees,
  employeeId,
  employee,
  onSelectEmployee,
  activeJobTitle,
  onNotificationAction,
  secondaryPanel,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const path = useRouterState({ select: (state) => state.location.pathname });
  // Somebody who has accepted an offer and not started. The field is the honest answer and
  // is absent from the mock the browser falls back to when the API is down, so being on the
  // page counts too — otherwise the link vanishes from under somebody standing on it.
  const joining =
    employee?.employment_status === "Onboarding" || path.startsWith("/onboarding");
  const navigate = useNavigate();

  /**
   * Switching person goes home.
   *
   * Everything on screen belongs to whoever was selected a moment ago — the conversation,
   * the documents outstanding, the requests. Staying put after a switch leaves somebody
   * looking at a page that has quietly become about a different person, and the chat is
   * the worst of it: the thread is keyed to the employee, so it empties out and reads as
   * though the conversation was lost. Home is the one page that is always about whoever
   * is selected now.
   */
  const switchTo = (id: string) => {
    onSelectEmployee(id);
    setMobileNavOpen(false);
    if (path === "/") return;

    // Onboarding is the exception to going home, when the person switched to is also a new
    // joiner. The rule above exists because a page quietly becomes about somebody else;
    // here it stays about the same *kind* of person, and the page redraws around them.
    // Bouncing between two joiners is how you compare them, and going home each time makes
    // that three clicks instead of one. Switching to somebody who has started still goes
    // home, because there is nothing on this page for them.
    const next = employees.find((person) => person.id === id || person.user_id === id);
    if (path.startsWith("/onboarding") && next?.employment_status === "Onboarding") return;

    void navigate({ to: "/" });
  };

  const navigation = (
    <nav aria-label="Sections" className="space-y-1 p-2">
      {NAV.filter((item) => !item.joinersOnly || joining).map(
        ({ to, label, icon: Icon }) => {
        const current = to === "/" ? path === "/" : path.startsWith(to);
        return (
          <Link
            key={to}
            to={to}
            onClick={() => setMobileNavOpen(false)}
            aria-current={current ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              current
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" aria-hidden="true" />
            {label}
          </Link>
        );
        },
      )}
    </nav>
  );

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex shrink-0 items-center gap-3 border-b bg-card px-3 py-2.5 sm:px-4">
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="lg:hidden cursor-pointer"
              aria-label="Open menu"
            >
              <PanelLeft aria-hidden="true" className="size-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[300px] p-0">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b p-2">
                <UserSwitcher
                  activeJobTitle={activeJobTitle}
                  employees={employees}
                  activeId={employeeId}
                  onSelect={switchTo}
                  className="w-full justify-start"
                />
              </div>
              {navigation}
              {secondaryPanel && (
                <div className="min-h-0 flex-1 border-t">{secondaryPanel}</div>
              )}
            </div>
          </SheetContent>
        </Sheet>

        <Button
          variant="ghost"
          size="icon-sm"
          className="hidden lg:flex cursor-pointer text-muted-foreground hover:text-foreground"
          onClick={() => setSidebarOpen((open) => !open)}
          aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          <PanelLeft className="size-4" />
        </Button>

        <Link to="/" className="flex items-center gap-2.5">
          <InceptionLogo className="h-7.5 sm:h-8.5 w-auto shrink-0" />
          <div className="animate-brand-spin cursor-pointer select-none">
            <h1 className="font-display text-xl sm:text-2xl font-black tracking-tight bg-gradient-to-r from-foreground via-primary to-foreground bg-clip-text text-transparent hover:scale-105 transition-transform">
              {APP_TITLE}
            </h1>
          </div>
        </Link>

        <div className="min-w-0 flex-1" />

        <div className="flex items-center gap-2">
          <NotificationCenter
            employeeId={employeeId}
            {...(employee ? { employee } : {})}
            {...(onNotificationAction ? { onActionClick: onNotificationAction } : {})}
          />
          <UserSwitcher
            activeJobTitle={activeJobTitle}
            employees={employees}
            activeId={employeeId}
            onSelect={switchTo}
          />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {sidebarOpen && (
          <aside className="hidden w-[260px] shrink-0 flex-col border-r bg-sidebar lg:flex">
            {navigation}
            {secondaryPanel && (
              <div className="min-h-0 flex-1 border-t">{secondaryPanel}</div>
            )}
          </aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
