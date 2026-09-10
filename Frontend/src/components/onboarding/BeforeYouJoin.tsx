import { Link } from "@tanstack/react-router";
import { ChevronRight, Sparkles } from "lucide-react";

/**
 * The questions new joiners ask, and only the ones that have an answer.
 *
 * Each of these is answered by a clause of HC-PC-013, named beside it. That is the whole
 * selection rule: a question on this page must be one the assistant can answer from the
 * People Code. A tile that leads to "that is not in the People Code, please contact People
 * & Culture" is worse than no tile — it looks broken, and it wastes the tap.
 *
 * Two obvious-sounding questions are deliberately absent. "What happens after visa
 * approval?" has no answer because there is no approval state and §13.1 puts everything
 * after the first day out of scope. "When will I sign my contract?" has no clause anywhere
 * in the Code — every mention of a contract is about precedence, probation length or how
 * salary is defined. Both belong here the day the policy covers them, and not before.
 *
 * The contract is worth a second look, because HCS-11 now issues one and takes the
 * signature on screen — and that changed nothing here. Knowing where somebody's contract
 * has got to is a fact; knowing what the rules around signing it are is a policy, and
 * there is still no policy. The board above says where they are, and this list stays as it
 * was until the Code has something to answer with.
 */
const QUESTIONS: { ask: string; clause: string }[] = [
  { ask: "Which documents do I need to send?", clause: "§13.4" },
  { ask: "Where do I send my visa documents?", clause: "§13.5" },
  { ask: "What is the deadline for my documents?", clause: "§13.6" },
  // Named as a *visa* document on purpose. Asked as "what happens if a document comes
  // back?" this was answered with a clarifying question — reasonably, since the employee
  // could mean a school document, an expense receipt or a medical certificate. A question
  // on a tile has no conversation behind it, so it has to carry its own context.
  { ask: "What happens if one of my visa documents is returned?", clause: "§13.8" },
  { ask: "Which visa route am I on?", clause: "§13.3" },
  { ask: "Do I get any leave before I start?", clause: "§13.2" },
];

export function BeforeYouJoin() {
  return (
    <section className="rounded-xl border bg-card">
      <div className="flex items-start gap-3 border-b px-4 py-3">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
        <div>
          <h3 className="font-display text-base font-semibold">Before you join</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            The questions new joiners ask most
          </p>
        </div>
      </div>

      <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
        {QUESTIONS.map(({ ask }) => (
          <Link
            key={ask}
            to="/chat"
            search={{ q: ask }}
            className="group flex items-center justify-between gap-2 rounded-lg border px-3 py-2.5 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
          >
            <span className="text-xs text-foreground">{ask}</span>
            <ChevronRight
              className="size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}
