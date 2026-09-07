import {
  CalendarCheck2,
  GraduationCap,
  HeartPulse,
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
  isSpecialAction?: boolean;
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
    isSpecialAction: true,
  },
  {
    id: "medical",
    title: "Medical Insurance",
    description: "Check medical coverage and claims",
    icon: HeartPulse,
    prompt: "What does my health insurance cover and what are the hospital network tiers?",
    colorClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    borderClass: "hover:border-sky-500/50 hover:bg-sky-500/5",
  },
  {
    id: "visa",
    title: "Visa & Residency",
    description: "Manage visas and residency renewals",
    icon: PlaneTakeoff,
    prompt: "What are the requirements for UAE visa renewal and family dependent sponsorship?",
    colorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    borderClass: "hover:border-amber-500/50 hover:bg-amber-500/5",
  },
];

interface AgenticCapabilitiesProps {
  onSelectCapability: (prompt: string) => void;
  onOpenSchoolUpload?: () => void;
  disabled?: boolean;
  className?: string;
}

export function AgenticCapabilities({
  onSelectCapability,
  onOpenSchoolUpload,
  disabled,
  className,
}: AgenticCapabilitiesProps) {
  return (
    <div className={cn("w-full", className)}>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {AGENTIC_CAPABILITIES.map((cap) => {
          const Icon = cap.icon;
          return (
            <div
              key={cap.id}
              role="button"
              tabIndex={0}
              onClick={() => {
                if (disabled) return;
                if (cap.isSpecialAction && onOpenSchoolUpload) {
                  onOpenSchoolUpload();
                } else {
                  onSelectCapability(cap.prompt);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  if (disabled) return;
                  if (cap.isSpecialAction && onOpenSchoolUpload) {
                    onOpenSchoolUpload();
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
