import { CheckCircle2, Circle, Clock, MinusCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JoiningStep, StepState } from "@/lib/home";

/**
 * Where a new joiner has got to, on the way to their first day.
 *
 * The steps and their states are worked out in `joiningSteps`, which is where the argument
 * about what can honestly be shown lives. This draws them and nothing more — in
 * particular it computes no percentage, because one of the steps is not tracked by either
 * system and a figure spanning it would be part invention.
 */
const LOOK: Record<StepState, { icon: typeof CheckCircle2; dot: string; label: string }> = {
  done: { icon: CheckCircle2, dot: "text-emerald-600", label: "text-foreground" },
  current: { icon: Clock, dot: "text-primary", label: "text-foreground font-semibold" },
  waiting: { icon: Circle, dot: "text-muted-foreground/30", label: "text-muted-foreground" },
  // Deliberately different from "waiting": nothing is coming, because nothing is watched.
  untracked: { icon: MinusCircle, dot: "text-muted-foreground/25", label: "text-muted-foreground/70" },
};

export function JoiningTimeline({ steps }: { steps: JoiningStep[] }) {
  // The first step somebody can act on. There can be more than one — an unsigned contract
  // and outstanding documents are both things to do today, and HCS-11 does not enforce an
  // order between them — so this takes the earliest rather than assuming a single one.
  // Untracked steps are skipped by construction: they are never `current`, because nothing
  // will ever complete them and nothing can be done about them.
  const current = steps.find((step) => step.state === "current");

  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-display text-base font-semibold">Your joining</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {/* The step by name, not a percentage. */}
          {current ? (
            <>
              Current step: <span className="text-foreground">{current.label}</span> ·{" "}
              {current.detail}
            </>
          ) : (
            // Only reachable when nothing is current and nothing is outstanding. Every
            // case with a fault on it now marks the documents step current instead, so
            // this cannot be shown over a claim that needs something.
            "Everything on your side is done."
          )}
        </p>
      </div>

      <ol className="flex flex-col gap-0 p-4 sm:flex-row sm:gap-2">
        {steps.map((step, index) => {
          const look = LOOK[step.state];
          const Icon = look.icon;
          const last = index === steps.length - 1;

          return (
            <li key={step.key} className="flex flex-1 gap-3 sm:flex-col sm:gap-2">
              {/* the rail: a line down the side on narrow screens, across on wide ones */}
              <div className="flex flex-col items-center sm:w-full sm:flex-row">
                <Icon className={cn("size-4 shrink-0", look.dot)} aria-hidden="true" />
                {!last && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "w-px flex-1 sm:h-px sm:w-full",
                      step.state === "done" ? "bg-emerald-600/40" : "bg-border",
                    )}
                  />
                )}
              </div>

              <div className={cn("min-w-0 pb-4 sm:pb-0", last && "pb-0")}>
                <p className={cn("text-xs leading-tight", look.label)}>{step.label}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
                  {step.detail}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
