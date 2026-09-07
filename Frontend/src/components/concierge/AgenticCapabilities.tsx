import {
  ArrowUpRight,
  Bot,
  CalendarCheck2,
  GraduationCap,
  HeartPulse,
  PlaneTakeoff,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgenticCapability {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  badge: string;
  icon: typeof CalendarCheck2;
  actionText: string;
  prompt: string;
  colorClass: string;
  borderClass: string;
  badgeClass: string;
  isSpecialAction?: boolean;
}

export const AGENTIC_CAPABILITIES: AgenticCapability[] = [
  {
    id: "leave-agent",
    title: "LeavePilot AI",
    subtitle: "Leaves & Vacation Co-Pilot",
    description:
      "Automated leave applications, real-time balance calculations, Outlook calendar deep-links & manager approval cards.",
    badge: "Autonomous Agent",
    icon: CalendarCheck2,
    actionText: "Apply for Leave",
    prompt: "I want to apply for leave",
    colorClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    borderClass: "hover:border-emerald-500/40 hover:bg-emerald-500/5",
    badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  },
  {
    id: "school-verification",
    title: "EduBenefit AI (HCS-11)",
    subtitle: "Kids Schooling & Tuition",
    description:
      "Multimodal Vision OCR extraction, UAE school accreditation checks, child age validation (4–18) & tuition fee cap matching.",
    badge: "Multimodal Vision OCR",
    icon: GraduationCap,
    actionText: "Upload & Verify Certificate",
    prompt: "I want to submit school certificates for child education benefits",
    colorClass: "bg-pink-500/10 text-pink-600 dark:text-pink-400",
    borderClass: "hover:border-pink-500/40 hover:bg-pink-500/5",
    badgeClass: "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/20",
    isSpecialAction: true,
  },
  {
    id: "medical-insurance",
    title: "CareShield Medical",
    subtitle: "Health Insurance & Claims",
    description:
      "Instant in-network clinic & hospital lookup, prescription co-pay guidelines, emergency coverage & direct billing assistance.",
    badge: "Policy & Network RAG",
    icon: HeartPulse,
    actionText: "Check Medical Coverage",
    prompt: "What does my health insurance cover and what are the hospital network tiers?",
    colorClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400",
    borderClass: "hover:border-sky-500/40 hover:bg-sky-500/5",
    badgeClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
  },
  {
    id: "visa-mobility",
    title: "VisaPass Mobility",
    subtitle: "Visa & Residency Navigator",
    description:
      "UAE residence visa renewals, dependent sponsorship guidelines, Golden Visa qualification checks & labor contract tracking.",
    badge: "Immigration & Compliance",
    icon: PlaneTakeoff,
    actionText: "Explore Visa Services",
    prompt: "What are the requirements for UAE visa renewal and family dependent sponsorship?",
    colorClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    borderClass: "hover:border-amber-500/40 hover:bg-amber-500/5",
    badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
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
    <div className={cn("w-full space-y-4", className)}>
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-primary" />
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Core Agentic Capabilities
          </span>
        </div>
        <span className="text-[11px] text-muted-foreground hidden sm:inline-flex items-center gap-1">
          <Sparkles className="size-3 text-primary" /> Click any card to launch agent
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
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
                "group relative flex flex-col justify-between rounded-2xl border border-border/80 bg-card/85 p-4.5 text-left transition-all duration-300 shadow-xs cursor-pointer hover:shadow-md hover:-translate-y-0.5",
                cap.borderClass,
                disabled && "opacity-50 pointer-events-none"
              )}
            >
              <div>
                {/* Header: Icon + Badge */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div
                    className={cn(
                      "flex size-10 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110",
                      cap.colorClass
                    )}
                  >
                    <Icon className="size-5" />
                  </div>
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold",
                      cap.badgeClass
                    )}
                  >
                    {cap.badge}
                  </span>
                </div>

                {/* Title & Subtitle */}
                <h3 className="font-display text-base font-bold text-foreground group-hover:text-primary transition-colors">
                  {cap.title}
                </h3>
                <p className="text-[11px] font-medium text-muted-foreground/80 mb-2">
                  {cap.subtitle}
                </p>

                {/* Description */}
                <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3 mb-4">
                  {cap.description}
                </p>
              </div>

              {/* Bottom Action Indicator */}
              <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs font-medium text-foreground/80 group-hover:text-primary transition-colors">
                <span>{cap.actionText}</span>
                <ArrowUpRight className="size-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
