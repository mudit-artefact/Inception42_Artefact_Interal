import { Link } from "@tanstack/react-router";
import {
  CalendarDays,
  ChevronRight,
  FileSignature,
  GraduationCap,
  PlaneTakeoff,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

/**
 * One thing this person has to do.
 *
 * `done`/`total` are the documents actually received against the ones their route needs —
 * both counted by the server from what HCS-11 sent, never from a list kept here. A visa
 * route asks for three, four or five documents depending on the person, so anything
 * hardcoded would be wrong for somebody.
 */
export interface ActionCard {
  key: string;
  kind: "visa" | "school" | "approval" | "contract";
  title: string;
  detail: string;
  badge: string;
  done?: number;
  total?: number;
  /** What to say to the assistant when this card is opened. */
  prompt: string;
}

const LOOK: Record<
  ActionCard["kind"],
  { icon: LucideIcon; tint: string; badge: string; border: string }
> = {
  contract: {
    icon: FileSignature,
    tint: "bg-primary/10 text-primary",
    badge: "bg-primary/15 text-primary",
    border: "border-primary/25 bg-primary/[0.04]",
  },
  visa: {
    icon: PlaneTakeoff,
    tint: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    badge: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
    border: "border-amber-500/25 bg-amber-500/[0.04]",
  },
  school: {
    icon: GraduationCap,
    tint: "bg-pink-500/10 text-pink-600 dark:text-pink-400",
    badge: "bg-pink-500/15 text-pink-700 dark:text-pink-300",
    border: "border-pink-500/25 bg-pink-500/[0.04]",
  },
  approval: {
    icon: CalendarDays,
    tint: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    badge: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
    border: "border-sky-500/25 bg-sky-500/[0.04]",
  },
};

export function ActionCards({ cards }: { cards: ActionCard[] }) {
  if (cards.length === 0) {
    return (
      <p className="px-4 py-8 text-center text-sm text-muted-foreground">
        Nothing to do right now.
      </p>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {cards.map((card) => {
        const look = LOOK[card.kind];
        const Icon = look.icon;
        const counted = typeof card.done === "number" && typeof card.total === "number";

        return (
          <Link
            key={card.key}
            to="/chat"
            search={{ q: card.prompt }}
            className={cn(
              "group flex flex-col gap-3 rounded-xl border p-4 text-left transition-all",
              "hover:-translate-y-0.5 hover:shadow-sm",
              look.border,
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-lg",
                  look.tint,
                )}
              >
                <Icon className="size-4.5" aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">{card.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{card.detail}</p>
                <Badge
                  variant="secondary"
                  className={cn("mt-2 font-normal", look.badge)}
                >
                  {card.badge}
                </Badge>
              </div>
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </div>

            {counted && (
              <div className="flex items-center gap-3">
                <Progress
                  value={card.total ? (card.done! / card.total) * 100 : 0}
                  className="h-1.5 flex-1"
                />
                <span className="shrink-0 text-xs text-muted-foreground">
                  {card.done} of {card.total}
                </span>
              </div>
            )}
          </Link>
        );
      })}
    </div>
  );
}
