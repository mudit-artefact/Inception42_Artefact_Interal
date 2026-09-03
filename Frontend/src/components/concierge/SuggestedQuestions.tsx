import { ArrowUpRight } from "lucide-react";

interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export function SuggestedQuestions({ questions, onSelect, disabled }: SuggestedQuestionsProps) {
  return (
    <div className="w-full">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        FAQs
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(q)}
            className="group flex w-full items-center justify-between gap-2 rounded-xl border bg-card/90 px-3.5 py-2 text-left text-xs text-foreground transition-all hover:border-pink/50 hover:bg-accent/60 hover:shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer shadow-2xs"
          >
            <span className="line-clamp-1 font-medium text-foreground group-hover:text-foreground">
              {q}
            </span>
            <ArrowUpRight
              aria-hidden="true"
              className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-foreground"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
