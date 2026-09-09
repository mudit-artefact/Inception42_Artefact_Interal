import type { LeaveRequestRow } from "@/lib/api/employee";
import type { CaseSummary } from "@/lib/api/hcs11";
import type { VisaCase } from "@/lib/api/visa";

/**
 * The three kinds of thing an employee asks for, on one list.
 *
 * They come from three systems that do not share a vocabulary. Leave says
 * `Approved / Pending / Rejected / Cancelled`; a schooling claim says
 * `Awaiting Submission / Under Review / Approved / Rejected`; a visa case says
 * `Ready for the PRO`. The design showed a fourth vocabulary — "In review", "In progress" —
 * that none of them uses.
 *
 * So none is invented here. **Each row shows the word its own system uses**, and only the
 * colour is worked out, from a short list of the words that mean "finished" and the words
 * that mean "you have something to do". A word nobody has classified is shown plainly
 * rather than guessed at — the wrong colour on a status is how a screen ends up telling
 * somebody their claim is fine.
 */
export type Tone = "done" | "attention" | "progress" | "waiting";

const FINISHED = new Set(["approved", "ready for the pro", "paid", "sent", "cancelled"]);
const NEEDS_YOU = new Set([
  "awaiting submission",
  "information requested",
  "rejected",
  "action needed",
]);
const WITH_US = new Set(["under review", "pending review", "pending", "in progress"]);

export function toneFor(status: string): Tone {
  const word = status.trim().toLowerCase();
  if (FINISHED.has(word)) return "done";
  if (NEEDS_YOU.has(word)) return "attention";
  if (WITH_US.has(word)) return "progress";
  return "waiting";
}

export interface RequestRow {
  key: string;
  title: string;
  detail: string;
  type: "Leave" | "Kids schooling" | "Employment visa";
  submitted: string;
  status: string;
  tone: Tone;
}

/** "2026-01-12" as "12 Jan 2026". Anything unparseable is passed through untouched. */
export function readableDate(value: string | null | undefined): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function span(start: string, end: string): string {
  const from = readableDate(start);
  const to = readableDate(end);
  return from && to ? `${from} – ${to}` : from || to;
}

export function leaveRow(request: LeaveRequestRow): RequestRow {
  return {
    key: `leave-${request.id}`,
    title: request.leave_type,
    detail: span(request.start_date, request.end_date),
    type: "Leave",
    submitted: readableDate(request.created_at),
    status: request.status,
    tone: toneFor(request.status),
  };
}

export function schoolRow(claim: CaseSummary): RequestRow {
  return {
    key: `school-${claim.case_id}`,
    title: "Schooling verification",
    detail: claim.dependent_name || claim.academic_year || "",
    type: "Kids schooling",
    submitted: readableDate(claim.submitted_on),
    status: claim.case_status,
    tone: toneFor(claim.case_status),
  };
}

export function visaRow(application: VisaCase): RequestRow {
  return {
    key: `visa-${application.case_id}`,
    title: "Employment visa",
    detail: application.plan_name ?? "",
    type: "Employment visa",
    submitted: readableDate(application.submitted_on),
    status: application.case_status,
    tone: toneFor(application.case_status),
  };
}
