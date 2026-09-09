import { Link, useRouterState } from "@tanstack/react-router";
import { Home, MessageSquare, PanelLeft } from "lucide-react";
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
  { to: "/", label: "Home", icon: Home },
  { to: "/chat", label: "Conversations", icon: MessageSquare },
] as const;

interface AppShellProps {
  employees: EmployeeProfile[];
  employeeId: string;
  employee: EmployeeProfile | null;
  onSelectEmployee: (id: string) => void;
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
  onNotificationAction,
  secondaryPanel,
  children,
}: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const path = useRouterState({ select: (state) => state.location.pathname });

  const navigation = (
    <nav aria-label="Sections" className="space-y-1 p-2">
      {NAV.map(({ to, label, icon: Icon }) => {
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
      })}
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
                  employees={employees}
                  activeId={employeeId}
                  onSelect={onSelectEmployee}
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
            employees={employees}
            activeId={employeeId}
            onSelect={onSelectEmployee}
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
