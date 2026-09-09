import type { PendingApproval, LeaveRequestRow } from "@/lib/api/employee";
import type { CaseDetailResponse, CaseSummary } from "@/lib/api/hcs11";
import type { VisaCase } from "@/lib/api/visa";
import type { ActionCard } from "@/components/home/ActionCards";
import { leaveRow, schoolRow, visaRow, type RequestRow } from "@/lib/requests";

/**
 * The one sentence the assistant understands for a manager's queue.
 *
 * There is no "show me request 17" intent on the server — only list, approve and reject.
 * Naming a single request would be classified as something else and answered worse, so the
 * card names the person in its own text and the chat opens the list, where each request
 * carries its own Approve and Reject buttons.
 */
const LIST_APPROVALS = "What leave requests do I need to approve?";

/** Documents still to send, named the way HCS-11 names them. */
function outstanding(application: VisaCase): string[] {
  const labels = new Map(
    (application.required_documents ?? []).map((row) => [row.kind, row.label]),
  );
  return (application.missing_documents ?? []).map((kind) => labels.get(kind) ?? kind);
}

function sentence(names: string[]): string {
  if (names.length === 0) return "Everything has been sent";
  const [first] = names;
  if (names.length === 1) return `Upload your ${first!.toLowerCase()}`;
  return `Upload your ${first!.toLowerCase()}, and ${names.length - 1} more`;
}

export function buildActionCards(sources: {
  visaCases?: VisaCase[] | undefined;
  openSchoolCase?: CaseDetailResponse | null | undefined;
  approvals?: PendingApproval[] | undefined;
}): ActionCard[] {
  const cards: ActionCard[] = [];

  for (const application of sources.visaCases ?? []) {
    const missing = outstanding(application);
    const total = application.required_documents?.length ?? 0;
    // Nothing outstanding and nothing wrong is not something to do.
    if (missing.length === 0 && (application.problems?.length ?? 0) === 0) continue;
    cards.push({
      key: `visa-${application.case_id}`,
      kind: "visa",
      title: "Employment visa",
      detail: application.problems?.[0] ?? sentence(missing),
      badge: missing.length > 0 ? "Document needed" : "Needs attention",
      done: total - missing.length,
      total,
      // Phrased as a request to send, not a question about what is outstanding.
      // "What do I still need to send…" reads as a question, is classified as one, and
      // gets answered with a list — leaving somebody who tapped an Upload card reading
      // prose instead of looking at the upload window they asked for.
      prompt: "I want to upload my visa documents",
    });
  }

  const claim = sources.openSchoolCase;
  if (claim && !claim.everything_is_settled) {
    // The server has already worked out which documents arrived and which have a problem —
    // the same reading the upload panel shows. Counting them again here is how the two
    // screens would come to disagree.
    const rows = claim.documents ?? [];
    const received = rows.filter((row) => row.received).length;
    const faulty = rows.filter((row) => row.has_issues);
    cards.push({
      key: `school-${claim.case.case_id}`,
      kind: "school",
      title: "Schooling verification",
      detail:
        faulty[0]?.issue_message ??
        claim.problems?.[0] ??
        (received < rows.length
          ? `${rows.length - received} document${rows.length - received === 1 ? "" : "s"} still to send`
          : "Confirm your school documents"),
      badge: faulty.length > 0 ? "Action needed" : "In review",
      done: received,
      total: rows.length,
      prompt: "I want to upload my school documents",
    });
  }

  for (const approval of sources.approvals ?? []) {
    cards.push({
      key: `approval-${approval.request_id}`,
      kind: "approval",
      title: "Leave to approve",
      detail: `${approval.employee_name} · ${approval.days_requested} day${
        approval.days_requested === 1 ? "" : "s"
      } ${approval.leave_type.toLowerCase()}`,
      badge: "Waiting for you",
      prompt: LIST_APPROVALS,
    });
  }

  return cards;
}

export function buildRequestRows(sources: {
  leaveRequests?: LeaveRequestRow[] | undefined;
  schoolCases?: CaseSummary[] | undefined;
  visaCases?: VisaCase[] | undefined;
}): RequestRow[] {
  return [
    ...(sources.leaveRequests ?? []).map(leaveRow),
    ...(sources.schoolCases ?? []).map(schoolRow),
    ...(sources.visaCases ?? []).map(visaRow),
  ];
}
