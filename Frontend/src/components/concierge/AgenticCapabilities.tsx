import {
  CalendarCheck2,
  FileSignature,
  GraduationCap,
  PlaneTakeoff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { whatTheyCanDo, type Doable } from "@/lib/whatTheyCanDo";
import type { EmployeeProfile } from "@/lib/api/types";

export interface AgenticCapability {
  id: string;
  title: string;
  description: string;
  icon: typeof CalendarCheck2;
  prompt: string;
  colorClass: string;
  borderClass: string;
  /**
   * What this person has to be able to do for the tile to be worth offering.
   *
   * All four used to be shown to everybody, so a new joiner was offered leave she cannot
   * take and a five-year employee was offered a visa case he does not have. Each tile now
   * says what it is for and `whatTheyCanDo` decides who sees it.
   */
  needs: Doable;
  /**
   * Which panel this tile opens, if it opens one rather than asking a question.
   *
   * This was a boolean called `isSpecialAction`, which could say that a tile was special
   * but not which special thing it did — one bit for what are now three destinations.
   */
  opens?: "school-documents" | "visa-documents" | "contract";
}

export const AGENTIC_CAPABILITIES: AgenticCapability[] = [
  {
    id: "leaves",
    needs: "leave",
    title: "Leaves",
    description: "Apply and track leave requests",
    icon: CalendarCheck2,
    prompt: "I want to apply for leave",
    colorClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    borderClass: "hover:border-emerald-500/50 hover:bg-emerald-500/5",
  },
  {
    id: "schooling",
    needs: "schooling",
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
    // Opens rather than asks, like the two document tiles. "When will I sign?" would be a
    // question, and the People Code has no clause about signing a contract to answer it
    // with — but where somebody's own contract has got to is a fact HCS-11 holds, and the
    // panel is the honest way to show it.
    id: "contract",
    needs: "contract",
    title: "Employment Contract",
    description: "Read and sign your contract",
    icon: FileSignature,
    prompt: "I want to sign my contract",
    colorClass: "bg-primary/10 text-primary",
    borderClass: "hover:border-primary/50 hover:bg-primary/5",
    opens: "contract",
  },
  {
    // Renewal and family sponsorship are not in the People Code, and the assistant
    // correctly declines them. What it does have is HC-PC-013: the documents a new joiner
    // provides before their first day. The tile now says that.
    id: "visa",
    needs: "visa",
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
  /** Who is looking. Without them, nothing is offered rather than everything. */
  employee?: EmployeeProfile | null | undefined;
}

export function AgenticCapabilities({
  onSelectCapability,
  onOpenPanel,
  disabled,
  className,
  employee,
}: AgenticCapabilitiesProps) {
  const canDo = whatTheyCanDo(employee);
  const offered = AGENTIC_CAPABILITIES.filter((cap) => canDo.has(cap.needs));

  // Before the directory answers there is nobody, and nobody can do anything. Drawing
  // nothing for that moment is right: an empty space reads as loading, where the wrong
  // four tiles read as an answer.
  if (offered.length === 0) return null;

  return (
    <div className={cn("w-full", className)}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {offered.map((cap) => {
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
