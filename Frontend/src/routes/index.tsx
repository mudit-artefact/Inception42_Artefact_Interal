import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, FileText, ListChecks, Loader2, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { ActionCards } from "@/components/home/ActionCards";
import { NewChatBox } from "@/components/home/NewChatBox";
import { RequestsTable } from "@/components/home/RequestsTable";
import { AppShell, APP_TITLE } from "@/components/layout/AppShell";
import { useActiveEmployee } from "@/hooks/useActiveEmployee";
import { fetchLeaveRequests, fetchPendingApprovals } from "@/lib/api/employee";
import { getActiveCase, getEmployeeCases } from "@/lib/api/hcs11";
import { getVisaCases } from "@/lib/api/visa";
import { buildActionCards, buildRequestRows } from "@/lib/home";

const DESCRIPTION =
  "What needs your attention across your HR journey — your requests, your documents, and Dalīl when you need it.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: APP_TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: APP_TITLE },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: HomePage,
});

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function HomePage() {
  const { employees, employeeId, selectEmployee, employee } = useActiveEmployee();
  const [leaving, setLeaving] = useState(false);

  // Everything is asked for, and what comes back decides what is shown.
  //
  // This used to branch on `employment_status` and on a count of direct reports: a new
  // joiner was asked about their visa, everybody else about their schooling claim. That
  // reads well and fails badly. When the profile does not carry those fields — an older
  // backend, a mock, a person whose record is incomplete — the comparison is false rather
  // than unknown, so every new joiner was quietly treated as a current employee and never
  // shown the visa documents they had to send. A screen that hides a task because a field
  // was missing is the same failure as a screen that shows a green tick because a check
  // was unrecognised.
  //
  // The data already answers the question. A new joiner has a visa case and no schooling
  // claim; a current employee has the reverse; somebody who manages nobody has an empty
  // approvals list. Four requests instead of two, and no way to guess wrong.
  const ready = Boolean(employeeId);
  const visa = useQuery({
    queryKey: ["visa-cases", employeeId],
    queryFn: () => getVisaCases(employeeId),
    enabled: ready,
  });
  const school = useQuery({
    queryKey: ["school-cases", employeeId],
    queryFn: () => getEmployeeCases(employeeId),
    enabled: ready,
  });
  // The open claim, read the way an upload reads it. This endpoint used to return its
  // verdict fields empty — reporting "nothing wrong" whatever HCS-11 had decided — which
  // is exactly the failure a card built on it would have inherited.
  const openClaim = useQuery({
    queryKey: ["active-school-case", employeeId],
    queryFn: () => getActiveCase(employeeId),
    enabled: ready,
  });
  const leave = useQuery({
    queryKey: ["leave-requests", employeeId],
    queryFn: () => fetchLeaveRequests(employeeId),
    enabled: ready,
  });
  const approvals = useQuery({
    queryKey: ["approvals", employeeId],
    queryFn: () => fetchPendingApprovals(employeeId),
    enabled: ready,
  });

  const loading =
    visa.isLoading ||
    school.isLoading ||
    openClaim.isLoading ||
    leave.isLoading ||
    approvals.isLoading;
  // Every source that could not be reached. The page says so rather than drawing an empty
  // table, which would read as "you have no requests" — a different and untrue statement.
  const unreachable = [visa, school, openClaim, leave, approvals].some(
    (query) => query.isError,
  );

  const cards = buildActionCards({
    visaCases: visa.data,
    openSchoolCase: openClaim.data,
    approvals: approvals.data,
  });
  const rows = buildRequestRows({
    leaveRequests: leave.data,
    schoolCases: school.data,
    visaCases: visa.data,
  });

  const firstName = (employee?.name ?? "").split(" ")[0] ?? "";

  // Nothing here is new-joiner-only any more.
  //
  // The joining timeline and the "before you join" questions were the only two panels one
  // kind of person saw and another did not, and they now have a page of their own. What is
  // left is the same page for everybody: the cards under My tasks differ because the
  // *data* differs — a joiner has a contract to sign where a manager has leave to approve —
  // and that is a page reading its contents, not a page deciding who you are.
  return (
    <AppShell
      employees={employees}
      employeeId={employeeId}
      employee={employee}
      onSelectEmployee={selectEmployee}
      // The contract's title, not the record's. They differ for every new joiner, and a
      // header naming one job over a contract naming another is the disagreement showing
      // through rather than being settled.
      activeJobTitle={visa.data?.[0]?.contract?.job_title}
    >
      <motion.div
        animate={leaving ? { opacity: 0, scale: 0.985 } : { opacity: 1, scale: 1 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className="flex min-h-0 flex-1 flex-col bg-background"
      >
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 sm:px-6">
            <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
                  {greeting()}
                  {firstName ? `, ${firstName}` : ""}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Here is what needs your attention across your HR journey.
                </p>
              </div>
              <div className="flex items-start gap-3 rounded-xl border border-primary/20 bg-primary/[0.04] p-3 sm:max-w-sm">
                <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Your HR partner, whenever you need it.
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Get help, complete tasks and track your requests in one place.
                  </p>
              </div>
            </div>
          </header>

          {unreachable && (
            <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3">
              <AlertCircle
                className="mt-0.5 size-4 shrink-0 text-destructive"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-destructive">
                  Some of this could not be loaded
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  What is shown below may be incomplete. Nothing has been guessed at.
                </p>
              </div>
            </div>
          )}

          <section className="rounded-xl border bg-card">
            <div className="flex items-center justify-between border-b px-4 py-3">
              {/*
                "My tasks", not "Notifications".

                Every card under it is something to do — sign a contract, send documents,
                decide on somebody's leave — and each carries a button that does it. None of
                them is news. The bell in the header is where news goes, and having two
                things called notifications left the one that was actually a to-do list
                wearing the other one's name.

                The icon changed with it. An alert triangle over a list of ordinary tasks
                reads as a warning about all of them.
              */}
              <h3 className="flex items-center gap-2 font-display text-base font-semibold">
                <ListChecks className="size-4 text-primary" aria-hidden="true" />
                My tasks
              </h3>
            </div>
            <div className="p-4">
              {loading ? <Waiting /> : <ActionCards cards={cards} />}
            </div>
          </section>

          <section className="rounded-xl border bg-card">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="flex items-center gap-2 font-display text-base font-semibold">
                <FileText className="size-4 text-primary" aria-hidden="true" />
                My requests
              </h3>
            </div>
            {/* All of them. Truncating meant needing a second page to show the rest,
                and the rest was one row. */}
            {loading ? <Waiting /> : <RequestsTable rows={rows} />}
          </section>


          </div>
        </div>

        {/* Always in reach. It used to sit at the foot of the scrolling column, so on a
            dashboard with anything on it you had to scroll to the bottom to ask a
            question — the one thing that should never be somewhere you have to go and
            find. */}
        <div className="shrink-0 border-t bg-background/95 backdrop-blur">
          <div className="mx-auto w-full max-w-5xl px-4 py-3 sm:px-6">
            <NewChatBox onLeaving={() => setLeaving(true)} />
          </div>
        </div>
      </motion.div>
    </AppShell>
  );
}

function Waiting() {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      Loading…
    </div>
  );
}
