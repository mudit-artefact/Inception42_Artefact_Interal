import {
  ArrowUpRight,
  FileCheck2,
  HelpCircle,
  Home,
  RotateCcw,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface FAQItem {
  id: string;
  question: string;
  icon: typeof Home;
  colorClass: string;
}

export const DEFAULT_HR_FAQS: FAQItem[] = [
  {
    id: "wfh-policy",
    question: "Can I take work from home?",
    icon: Home,
    colorClass: "text-indigo-600 dark:text-indigo-400 bg-indigo-500/10",
  },
  {
    id: "line-manager",
    question: "Who is my line manager?",
    icon: UserCheck,
    colorClass: "text-sky-600 dark:text-sky-400 bg-sky-500/10",
  },
  {
    id: "carry-over",
    question: "Can I carry over unused leave into next year?",
    icon: RotateCcw,
    colorClass: "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10",
  },
];

interface SuggestedQuestionsProps {
  questions?: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
  className?: string;
}

export function SuggestedQuestions({
  questions,
  onSelect,
  disabled,
  className,
}: SuggestedQuestionsProps) {
  const items: FAQItem[] =
    questions && questions.length > 0
      ? questions.slice(0, 3).map((q, idx) => {
          const matchingDefault = DEFAULT_HR_FAQS.find(
            (d) => d.question.toLowerCase() === q.toLowerCase()
          );
          if (matchingDefault) return matchingDefault;
          return {
            id: `custom-faq-${idx}`,
            question: q,
            icon: HelpCircle,
            colorClass: "text-primary bg-primary/10",
          };
        })
      : DEFAULT_HR_FAQS;

  return (
    <div className={cn("w-full space-y-2", className)}>
      <div className="flex items-center gap-1.5 px-1">
        <Sparkles className="size-3 text-primary" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
          FAQs
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(item.question)}
              className="group flex items-center justify-between gap-2.5 rounded-xl border border-border/70 bg-card/90 px-3.5 py-2.5 text-left transition-all duration-200 hover:border-primary/50 hover:bg-primary/5 hover:shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer shadow-2xs"
            >
              <div className="flex min-w-0 flex-1 items-center gap-2.5">
                <div
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-105",
                    item.colorClass
                  )}
                >
                  <Icon className="size-3.5" />
                </div>
                <span className="text-xs font-medium leading-snug text-foreground group-hover:text-primary transition-colors line-clamp-2">
                  {item.question}
                </span>
              </div>
              <ArrowUpRight
                aria-hidden="true"
                className="size-3.5 shrink-0 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary"
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
