import { CalendarDays, UserRound, Users } from "lucide-react";
import type { EmployeeProfile } from "@/lib/api/types";
import type { VisaContract } from "@/lib/api/visa";
import { readableDate } from "@/lib/requests";

/**
 * Who is joining, who to ask, and how far along.
 *
 * The job title, start date and salary shown anywhere on this page come from the
 * **contract**, not from our own employee record. They disagree for every one of the six
 * joiners — one is a Director here and a Finance Manager on the contract she is being asked
 * to sign — and the contract is the document with her signature on it.
 *
 * The contact is her **manager**, said plainly. The design called for a People Partner and
 * there is no such thing in this system: no field, no table, no seeded value. A name
 * invented to fill the box would be the one thing on the page nobody could check.
 */
export function OnboardingHeader({
  employee,
  contract,
  progress,
}: {
  employee: EmployeeProfile | null;
  contract: VisaContract | null | undefined;
  progress: { done: number; total: number; percent: number };
}) {
  const title = contract?.job_title || employee?.jobTitle || employee?.role || "";
  const starts = contract?.start_date || employee?.start_date;

  return (
    <section className="grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_auto] lg:items-center">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
        >
          <UserRound className="size-5" />
        </span>
        <div className="min-w-0">
          <p className="font-display text-lg font-semibold">{employee?.name}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {[title, employee?.work_location].filter(Boolean).join(" · ")}
          </p>
          {starts && (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarDays className="size-3.5 shrink-0" aria-hidden="true" />
              Starting {readableDate(starts)}
            </p>
          )}
        </div>
      </div>

      {/* Their manager. Not a People Partner — we do not have one, and this says which. */}
      {employee?.manager && (
        <div className="flex items-start gap-3 sm:border-l sm:pl-4">
          <span
            aria-hidden="true"
            className="flex size-11 shrink-0 items-center justify-center rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400"
          >
            <Users className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Your manager</p>
            <p className="mt-0.5 text-sm font-semibold">{employee.manager}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Or ask Dalīl anything about joining
            </p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 sm:col-span-2 sm:border-t sm:pt-4 lg:col-span-1 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
        <ProgressRing percent={progress.percent} />
        <div className="min-w-0">
          <p className="text-sm font-semibold">{progress.percent}% complete</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {progress.done} of {progress.total} milestones done
          </p>
          {/*
            Said out loud, because the count is smaller than the board.

            Two of the seven steps can never be ticked — nothing tracks the medical, and
            Day 1 is a date. Counting them would leave somebody who has done everything
            stuck below a hundred with no way to move, so they are shown and not counted,
            and the difference is stated rather than left to be noticed.
          */}
          <p className="mt-1 text-[11px] text-muted-foreground/80">
            The medical and Day 1 are not counted — nothing tracks them
          </p>
        </div>
      </div>
    </section>
  );
}

/**
 * The ring. Hand-drawn because nothing circular exists in the product — `ui/progress` is a
 * bar, and the one chart component draws bars and lines.
 */
function ProgressRing({ percent }: { percent: number }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.min(100, Math.max(0, percent)) / 100) * circumference;

  return (
    <svg
      viewBox="0 0 64 64"
      className="size-16 shrink-0 -rotate-90"
      role="img"
      aria-label={`${percent} per cent complete`}
    >
      <circle
        cx="32"
        cy="32"
        r={radius}
        fill="none"
        strokeWidth="6"
        className="stroke-muted"
      />
      <circle
        cx="32"
        cy="32"
        r={radius}
        fill="none"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circumference - filled}`}
        className="stroke-primary transition-[stroke-dasharray] duration-500"
      />
    </svg>
  );
}
