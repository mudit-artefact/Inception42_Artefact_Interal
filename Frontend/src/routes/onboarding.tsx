import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertCircle, Loader2 } from "lucide-react";
import { BeforeYouJoin } from "@/components/onboarding/BeforeYouJoin";
import { OnboardingBoard } from "@/components/onboarding/OnboardingBoard";
import { OnboardingHeader } from "@/components/onboarding/OnboardingHeader";
import { AppShell, APP_TITLE } from "@/components/layout/AppShell";
import { useActiveEmployee } from "@/hooks/useActiveEmployee";
import { getVisaCases } from "@/lib/api/visa";
import { joiningProgress, joiningSteps } from "@/lib/home";

const DESCRIPTION =
  "Everything between accepting your offer and your first day — what you still have to do, what we are doing, and when you start.";

export const Route = createFileRoute("/onboarding")({
  head: () => ({
    meta: [
      { title: APP_TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: APP_TITLE },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: OnboardingPage,
});

/**
 * Where a new joiner is, on a page of its own.
 *
 * This used to be two panels bolted onto the home page — the only two things there that
 * one kind of person saw and another did not. Splitting them lets home be the same page
 * for everybody and lets joining have the room it needs; it is also the only way the
 * journey can grow a step without home growing with it.
 *
 * The visa case is fetched under the key the home page and the chat already use, so
 * arriving from either costs no request.
 */
function OnboardingPage() {
  const { employees, employeeId, selectEmployee, employee } = useActiveEmployee();

  const visa = useQuery({
    queryKey: ["visa-cases", employeeId],
    queryFn: () => getVisaCases(employeeId),
    enabled: Boolean(employeeId),
  });

  const application = visa.data?.[0];
  const contract = application?.contract ?? null;
  const steps = joiningSteps(employee?.start_date, application);
  const progress = joiningProgress(steps);

  // Two signals, not one. `employment_status` is the honest answer and is missing from the
  // mock the browser falls back to when the API is down; having a visa case is the same
  // fact arrived at from the other side. Either will do, because a page that hides itself
  // because one field did not arrive is the failure this project keeps meeting.
  const joining =
    employee?.employment_status === "Onboarding" || Boolean(visa.data?.length);

  return (
    <AppShell
      employees={employees}
      employeeId={employeeId}
      employee={employee}
      onSelectEmployee={selectEmployee}
      activeJobTitle={contract?.job_title}
    >
      <div className="min-h-0 flex-1 overflow-y-auto bg-background">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
          <header>
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
              My Onboarding
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Everything between accepting your offer and your first day.
            </p>
          </header>

          {visa.isLoading ? (
            <Waiting />
          ) : !joining ? (
            <NotJoining />
          ) : (
            <>
              {/*
                Said before the board, not instead of it. A case we could not read leaves
                every step at its "nothing known yet" reading, which is honest on its own
                but reads as "nothing has happened" — and for somebody who has sent four
                documents in, that is the wrong story told confidently.
              */}
              {visa.isError && (
                <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3">
                  <AlertCircle
                    className="mt-0.5 size-4 shrink-0 text-destructive"
                    aria-hidden="true"
                  />
                  <div>
                    <p className="text-sm font-medium text-destructive">
                      Your application could not be loaded
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      The steps below may be out of date. Nothing has been guessed at.
                    </p>
                  </div>
                </div>
              )}

              <OnboardingHeader
                employee={employee}
                contract={contract}
                progress={progress}
              />
              <OnboardingBoard steps={steps} />
              <BeforeYouJoin />
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function Waiting() {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      Loading…
    </div>
  );
}

/**
 * Somebody who has already started, who reached this address anyway.
 *
 * They have no navigation link to it — but a URL is a URL, and a page that renders an
 * empty board with every step greyed out would read as "your joining has stalled" to a
 * person who joined two years ago.
 */
function NotJoining() {
  return (
    <div className="rounded-xl border bg-card p-8 text-center">
      <p className="text-sm font-medium">You have already joined.</p>
      <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
        This page follows a new joiner from their offer to their first day. Yours is behind
        you — everything current is on your home page.
      </p>
      <Link
        to="/"
        className="mt-4 inline-flex rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
      >
        Go home
      </Link>
    </div>
  );
}
