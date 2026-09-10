import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Circle,
  Clock,
  FileSignature,
  FileText,
  MinusCircle,
  PlaneTakeoff,
  ScanLine,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { JoiningStep, StepPhase, StepState } from "@/lib/home";

/**
 * The joining journey as a board: what you do, what we do, and the day itself.
 *
 * This replaces the single horizontal rail that used to sit on the home page. The rail
 * fitted seven steps into one line by saying almost nothing about each; three columns give
 * every step room for the thing a new joiner actually wants to know — whether they are
 * waiting on themselves or on us, and what to press if it is them.
 *
 * The grouping is presentation. The steps, their order and their states are all worked out
 * in `joiningSteps`, which is where the argument about what can honestly be shown lives.
 */
const PHASES: { key: StepPhase; title: string; blurb: string; tint: string }[] = [
  {
    key: "before",
    title: "Before joining",
    blurb: "Complete your part before you start",
    tint: "border-primary/25 bg-primary/[0.04]",
  },
  {
    key: "processing",
    title: "HC processing",
    blurb: "Handled by our HR and support teams",
    tint: "border-sky-500/25 bg-sky-500/[0.04]",
  },
  {
    key: "ready",
    title: "Ready to join",
    blurb: "Get set for your first day",
    tint: "border-emerald-500/25 bg-emerald-500/[0.04]",
  },
];

const ICONS: Record<string, LucideIcon> = {
  offer: FileText,
  contract: FileSignature,
  documents: FileText,
  checked: ScanLine,
  visa: PlaneTakeoff,
  medical: Stethoscope,
  "day-one": CalendarDays,
};

/**
 * How each state looks, and what it is called.
 *
 * The words are ours rather than a system's, unlike the request list — no system has a
 * vocabulary for "where a joiner is in joining", because the journey spans two of them and
 * a policy. What each word rests on is a state computed in `joiningSteps` from a real
 * field, so the label is a reading of that and not a fourth vocabulary invented here.
 */
const LOOK: Record<
  StepState,
  { icon: LucideIcon; pill: string; dot: string; word: string }
> = {
  done: {
    icon: CheckCircle2,
    pill: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
    dot: "text-emerald-600",
    word: "Completed",
  },
  current: {
    icon: Clock,
    pill: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    dot: "text-primary",
    word: "Action required",
  },
  waiting: {
    icon: Circle,
    pill: "bg-muted text-muted-foreground",
    dot: "text-muted-foreground/40",
    word: "Not started",
  },
  // Deliberately unlike "waiting": nothing is coming, because nothing is watched.
  untracked: {
    icon: MinusCircle,
    pill: "bg-muted text-muted-foreground/70",
    dot: "text-muted-foreground/30",
    word: "Not tracked",
  },
};

export function OnboardingBoard({ steps }: { steps: JoiningStep[] }) {
  // Numbered across the whole board, not within a column: the mockup numbers them 1–7 and
  // so does every conversation about them.
  const numbered = steps.map((step, index) => ({ step, number: index + 1 }));

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {PHASES.map((phase) => {
        const mine = numbered.filter(({ step }) => step.phase === phase.key);
        if (mine.length === 0) return null;

        return (
          <section
            key={phase.key}
            className={cn("flex flex-col rounded-xl border", phase.tint)}
          >
            <div className="border-b border-inherit px-4 py-3">
              <h3 className="font-display text-base font-semibold">{phase.title}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">{phase.blurb}</p>
            </div>

            <ol className="flex flex-col gap-3 p-3">
              {mine.map(({ step, number }) => (
                <Milestone key={step.key} step={step} number={number} />
              ))}
            </ol>
          </section>
        );
      })}
    </div>
  );
}

function Milestone({ step, number }: { step: JoiningStep; number: number }) {
  const look = LOOK[step.state];
  const Icon = ICONS[step.key] ?? FileText;

  return (
    <li className="rounded-xl border bg-card p-3">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 w-4 shrink-0 text-xs font-semibold text-muted-foreground"
        >
          {number}
        </span>
        <span
          aria-hidden="true"
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted/60",
            look.dot,
          )}
        >
          <Icon className="size-4.5" />
        </span>

        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">{step.label}</p>

          <Badge variant="secondary" className={cn("mt-1.5 font-normal", look.pill)}>
            {look.word}
          </Badge>

          <p className="mt-1.5 text-xs text-muted-foreground">{step.detail}</p>

          <p className="mt-2 text-[11px] text-muted-foreground/80">
            Owner: <span className="text-muted-foreground">{step.owner}</span>
          </p>

          {step.action && (
            <Link
              to="/chat"
              search={{ q: step.action.prompt }}
              className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {step.action.label}
              <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>
    </li>
  );
}
