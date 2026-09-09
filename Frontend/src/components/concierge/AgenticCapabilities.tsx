import {
  CalendarCheck2,
  GraduationCap,
  PlaneTakeoff,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgenticCapability {
  id: string;
  title: string;
  description: string;
  icon: typeof CalendarCheck2;
  prompt: string;
  colorClass: string;
  borderClass: string;
  /**
   * Which panel this tile opens, if it opens one rather than asking a question.
   *
   * This was a boolean called `isSpecialAction`, which could say that a tile was special
   * but not which special thing it did — one bit for what is now two destinations.
   */
  opens?: "school-documents" | "visa-documents";
}

export const AGENTIC_CAPABILITIES: AgenticCapability[] = [
  {
    id: "leaves",
    title: "Leaves",
    description: "Apply and track leave requests",
    icon: CalendarCheck2,
    prompt: "I want to apply for leave",
    colorClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    borderClass: "hover:border-emerald-500/50 hover:bg-emerald-500/5",
  },
  {
    id: "schooling",
    title: "Kids Schooling",
    description: "Verify children school documents",
    icon: GraduationCap,
    prompt: "I want to submit school certificates for child education benefits",
    colorClass: "bg-pink-500/10 text-pink-600 dark:text-pink-400",
    borderClass: "hover:border-pink-500/50 hover:bg-pink-500/5",
    opens: "school-documents",
  },
  // Medical insurance was a fourth tile here, and there is no medical insurance policy in
  // the People Code to answer it from. Tapping it asked a question the assistant can only
  // decline — the same reason renewal and family sponsorship are not offered below. The
  // guard in `prompts.py` stays, so the answer is still a proper one if somebody types it.
  {
    // Renewal and family sponsorship are not in the People Code, and the assistant
    // correctly declines them. What it does have is HC-PC-013: the documents a new joiner
    // provides before their first day. The tile now says that.
    id: "visa",
    title: "Employment Visa",
    description: "Send your joining documents",
    icon: PlaneTakeoff,
    prompt: "What documents do I need for my employment visa?",
    colorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    borderClass: "hover:border-amber-500/50 hover:bg-amber-500/5",
    opens: "visa-documents",
  },
];

interface AgenticCapabilitiesProps {
  onSelectCapability: (prompt: string) => void;
  onOpenPanel?: (panel: NonNullable<AgenticCapability["opens"]>) => void;
  disabled?: boolean;
  className?: string;
}

export function AgenticCapabilities({
  onSelectCapability,
  onOpenPanel,
  disabled,
  className,
}: AgenticCapabilitiesProps) {
  return (
    <div className={cn("w-full", className)}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {AGENTIC_CAPABILITIES.map((cap) => {
          const Icon = cap.icon;
          return (
            <div
              key={cap.id}
              role="button"
              tabIndex={0}
              onClick={() => {
                if (disabled) return;
                if (cap.opens && onOpenPanel) {
                  onOpenPanel(cap.opens);
                } else {
                  onSelectCapability(cap.prompt);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (disabled) return;
                  if (cap.opens && onOpenPanel) {
                    onOpenPanel(cap.opens);
                  } else {
                    onSelectCapability(cap.prompt);
                  }
                }
              }}
              className={cn(
                "group relative flex flex-col items-start rounded-xl border border-border/70 bg-card/85 p-4 text-left transition-all duration-200 cursor-pointer hover:shadow-sm hover:-translate-y-0.5",
                cap.borderClass,
                disabled && "opacity-50 pointer-events-none"
              )}
            >
              <div
                className={cn(
                  "flex size-9 items-center justify-center rounded-lg mb-2.5 transition-transform duration-200 group-hover:scale-105",
                  cap.colorClass
                )}
              >
                <Icon className="size-4.5" />
              </div>
              <h3 className="font-display text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {cap.title}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground leading-snug">
                {cap.description}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
