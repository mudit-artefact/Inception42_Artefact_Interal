import { ArrowUpRight } from "lucide-react";

interface SuggestedQuestionsProps {
  questions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export function SuggestedQuestions({ questions, onSelect, disabled }: SuggestedQuestionsProps) {
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        FAQs
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {questions.map((q) => (
          <li key={q}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(q)}
              className="group inline-flex max-w-full items-center gap-1 rounded-full border bg-card px-3 py-1 text-left text-xs text-foreground transition-all hover:border-pink/50 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 cursor-pointer shadow-2xs"
            >
              <span className="font-normal text-foreground group-hover:text-foreground">
                {q}
              </span>
              <ArrowUpRight
                aria-hidden="true"
                className="size-3 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
