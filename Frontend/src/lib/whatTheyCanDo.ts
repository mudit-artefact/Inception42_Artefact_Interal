import type { EmployeeProfile } from "@/lib/api/types";

/**
 * What this person is actually able to do, so nothing is offered that would be refused.
 *
 * A new joiner saying "thank you" was asked whether she wanted to apply for leave. She
 * cannot — the assistant turns leave away from anybody who has not started and answers
 * "leave begins on your first day" — and the same offer was on the tiles, in the quick
 * actions, in the input placeholder and on a pill under any answer that mentioned the
 * word. Five surfaces offering one thing the sixth would decline.
 *
 * The split is by who they are, which is how people describe it and how the People Code
 * describes it: before your first day you are dealing with your visa and your contract,
 * and after it with your leave and your children's schooling. Managing people is a third
 * thing entirely and cuts across both.
 *
 * **This reads `employment_status` directly, with no fallback, and that is now safe.** It
 * was not before: the browser used to substitute twelve invented personas when the API
 * failed, none carrying the field, so an absent value compared as `false` rather than
 * unknown and every new joiner quietly became an employee. Those personas are gone, so the
 * field either arrives from the record or the page says it could not load.
 */
export type Doable =
  | "leave"
  | "approvals"
  | "schooling"
  | "visa"
  | "contract"
  | "attach-a-file";

const BEFORE_YOU_START: Doable[] = ["visa", "contract", "attach-a-file"];
const ONCE_YOU_HAVE = ["leave", "schooling", "attach-a-file"] as const;

export function whatTheyCanDo(employee: EmployeeProfile | null | undefined): Set<Doable> {
  // Nobody yet. Offer nothing rather than guessing — a moment of an empty row reads as
  // loading, where a wrong row reads as an answer.
  if (!employee) return new Set();

  const joining = employee.employment_status === "Onboarding";
  const doable: Doable[] = joining ? [...BEFORE_YOU_START] : [...ONCE_YOU_HAVE];

  // Neither a joiner's list nor an employee's, because managing people is not a stage of
  // employment. There is no "is a manager" flag in the system; having reports is what
  // being one means, and this is that, counted.
  if ((employee.direct_reports ?? 0) > 0) doable.push("approvals");

  return new Set(doable);
}

/** Whether one thing is on offer for this person. */
export function canThey(
  employee: EmployeeProfile | null | undefined,
  thing: Doable,
): boolean {
  return whatTheyCanDo(employee).has(thing);
}
