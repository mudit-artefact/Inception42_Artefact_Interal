import type { PendingApproval, LeaveRequestRow } from "@/lib/api/employee";
import type { CaseDetailResponse, CaseSummary } from "@/lib/api/hcs11";
import type { VisaCase } from "@/lib/api/visa";
import type { ActionCard } from "@/components/home/ActionCards";
import { leaveRow, readableDate, schoolRow, visaRow, type RequestRow } from "@/lib/requests";

/**
 * The one sentence the assistant understands for a manager's queue.
 *
 * There is no "show me request 17" intent on the server — only list, approve and reject.
 * Naming a single request would be classified as something else and answered worse, so the
 * card names the person in its own text and the chat opens the list, where each request
 * carries its own Approve and Reject buttons.
 */
/**
 * HCS-11's name for the signed job-offer form.
 *
 * It is on every route's checklist — both international routes and both resident ones —
 * and it is the one row a joiner does not upload: signing the contract files it for them.
 * So it belongs to the contract step of the journey and not to the documents step, even
 * though HCS-11 quite correctly counts it among the documents.
 */
const JOB_OFFER = "job_offer";

const LIST_APPROVALS = "What leave requests do I need to approve?";

/**
 * Documents still to send, named the way HCS-11 names them.
 *
 * The signed job-offer form is left out, because it is not sent — it is filed by signing
 * the contract. With it in, this card read "Upload your signed job-offer form, and 1 more"
 * to somebody who had a **Sign your contract** card sitting directly beside it offering to
 * do exactly that. One of the two was telling them to do the wrong thing.
 */
function outstanding(application: VisaCase): string[] {
  const labels = new Map(
    (application.required_documents ?? []).map((row) => [row.kind, row.label]),
  );
  return (application.missing_documents ?? [])
    .filter((kind) => kind !== JOB_OFFER)
    .map((kind) => labels.get(kind) ?? kind);
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
    // Signing comes first, and it is its own card rather than a line on the visa one:
    // it is a different action on a different document, and folding it in would put
    // "upload" on something nobody uploads.
    const contract = application.contract;
    if (contract && !contract.is_signed) {
      cards.push({
        key: `contract-${application.case_id}`,
        kind: "contract",
        title: "Employment contract",
        detail: contract.signed_on
          ? // A form on file that HCS-11 would not accept. Not signed, and not untouched.
            "A form on file has not been accepted — sign it here"
          : "Read it and sign — nothing to print",
        badge: "Signature needed",
        // Phrased as a request, like the two below: a question gets answered with prose
        // instead of the window the card promised.
        prompt: "I want to sign my contract",
      });
    }

    const missing = outstanding(application);
    // The papers, matching what `outstanding` lists. Counting the whole checklist against a
    // list the job-offer form had been taken out of made the bar disagree with the sentence
    // beside it — "upload your photograph, and 1 more" over a bar reading 1 of 3.
    const total = (application.required_documents ?? []).filter(
      (row) => row.kind !== JOB_OFFER,
    ).length;
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

// ── where a new joiner has got to ────────────────────────────────────────────

export type StepState = "done" | "current" | "waiting" | "untracked";

/** Which part of the journey a step belongs to, for the board that groups them. */
export type StepPhase = "before" | "processing" | "ready";

export interface JoiningStep {
  key: string;
  label: string;
  detail: string;
  state: StepState;
  phase: StepPhase;
  /**
   * Whose move it is. Static text, because no system holds a per-step owner — HCS-11's
   * three statuses say where a case *is*, not who has it. It is worth saying anyway: the
   * commonest question a new joiner asks is whether they are waiting on themselves or on
   * us, and the answer is a property of the process rather than of their case.
   */
  owner: string;
  /**
   * Whether this step counts towards the progress figure.
   *
   * Only Day 1 is excluded, and only because it is a date rather than a task — nobody
   * *does* their first day, they arrive at it.
   *
   * The medical counts even though nothing tracks it and nothing here can tick it, which
   * means the figure never reaches a hundred. That is the point. It was excluded at first
   * on the reasoning that a step which cannot complete should not hold the number down —
   * but the number is a claim about whether somebody is ready to join, and the medical is
   * real work standing between them and their first day. A hundred per cent over it would
   * be the page's most confident statement and its least true one.
   *
   * All of this replaces a flat refusal to show any percentage at all, whose objection was
   * that a figure spanning an untracked step is part invention. It is — so the untracked
   * step is named on the board and under the ring rather than quietly folded in.
   */
  counts: boolean;
  /** Something to do about it, said the way the assistant expects to be asked. */
  action?: { label: string; prompt: string };
}

/** How far along, over the steps that can actually finish. */
export function joiningProgress(steps: JoiningStep[]): {
  done: number;
  total: number;
  percent: number;
} {
  const counted = steps.filter((step) => step.counts);
  const done = counted.filter((step) => step.state === "done").length;
  const total = counted.length;
  return { done, total, percent: total === 0 ? 0 : Math.round((done / total) * 100) };
}

/**
 * The joining journey, as far as either system actually knows it.
 *
 * Every step below is read from a real field except one, and that one says so. The
 * temptation here is a tidy five-step rail with a percentage across it — and a percentage
 * over a step nobody tracks is a figure invented in part, shown first and read hardest.
 * There is no percentage.
 *
 * Three things this deliberately does not do, each of which looked reasonable first:
 *
 *  - **No "visa approved" step.** HCS-11 has three states and none of them is approval:
 *    awaiting the documents, held by HC Services, handed to the PRO. Nothing records that
 *    the officer lodged it and nothing records a government answer.
 *  - **No lodgement date.** `submitted_on` reads like "sent to the government" and means
 *    "the day your first document arrived" — it is set on the first upload, even a
 *    partial one.
 *  - **No tick on Day 1.** Nothing in either system ever flips it. It is a date.
 */
export function joiningSteps(
  startDate: string | undefined,
  visa: VisaCase | undefined,
): JoiningStep[] {
  // The whole checklist, job-offer form included. Kept for the "Documents checked" step
  // below: HC Services only assess a case when nothing at all is outstanding, so that step
  // has to wait for the contract too.
  const required = visa?.required_documents?.length ?? 0;
  const missing = visa?.missing_documents?.length ?? 0;
  const everythingIn = required > 0 && missing === 0;

  // And the same checklist without the job-offer form, which is what the documents step
  // counts.
  //
  // Signing the contract is what files that form, so it sits on every route's checklist as
  // a document — and counting it among the papers to send made the two steps circular. The
  // board recommends documents before the contract; before this split, "submit your
  // documents" could not reach the end of its own count until the step after it was done.
  const papersRequired = (visa?.required_documents ?? []).filter(
    (row) => row.kind !== JOB_OFFER,
  ).length;
  const papersMissing = (visa?.missing_documents ?? []).filter(
    (kind) => kind !== JOB_OFFER,
  ).length;
  const papersIn = papersRequired - papersMissing;
  const everyPaperIn = papersRequired > 0 && papersMissing === 0;
  const withThePro = visa?.case_status === "Ready for the PRO";
  // Held by a person because a check found something. HC-PC-013 §13.7.3.
  const heldForReview = visa?.case_status === "Under Review";
  // Assessed either way. A case that failed its checks has still been checked.
  const assessed = heldForReview || withThePro;
  // Something came back wrong and it is theirs to fix. §13.8.1: "Where a document is
  // returned, the new joiner removes it and submits a corrected copy."
  const somethingToCorrect = (visa?.problems?.length ?? 0) > 0;
  // Read `is_signed`, never `signed_on`: the date is set as soon as any job-offer form is
  // on the case, including an unsigned one, and the server has already asked HCS-11's own
  // check which it is.
  const contract = visa?.contract ?? null;

  return [
    {
      key: "offer",
      label: "Offer accepted",
      // No date. There is a real signed-on date, but it is read off the job-offer form
      // the joiner uploads — downstream of the documents step, not before it. Being a new
      // joiner is itself the evidence: §13.2 defines the status as "an accepted offer, a
      // start date agreed".
      detail: "Your start date is agreed",
      state: "done",
      phase: "before",
      owner: "You",
      counts: true,
    },
    {
      key: "documents",
      label: "Submit your documents",
      detail: somethingToCorrect
        ? "Something came back — send a corrected copy"
        : papersRequired > 0
          ? `${papersIn} of ${papersRequired} sent`
          : "Your checklist is loading",
      // Current again when something has to be re-sent. Every document having arrived is
      // not the same as every document being right, and marking this done with a fault
      // outstanding left the whole timeline with no current step at all — so the heading
      // read "Everything on your side is done" over a case with two problems on it.
      // Current again when something has to be re-sent. Every document having arrived is
      // not the same as every document being right, and marking this done with a fault
      // outstanding left the whole timeline with no current step at all — so the heading
      // read "Everything on your side is done" over a case with two problems on it.
      //
      // The counts here leave the job-offer form out; it belongs to the contract step
      // below. See `JOB_OFFER` — before that split, this step could not reach the end of
      // its own count until the step after it had been done.
      state: somethingToCorrect ? "current" : everyPaperIn ? "done" : "current",
      phase: "before",
      owner: "You",
      counts: true,
      ...(everyPaperIn && !somethingToCorrect
        ? {}
        : {
            action: {
              label: somethingToCorrect ? "Send a corrected copy" : "Continue",
              prompt: "I want to upload my visa documents",
            },
          }),
    },
    {
      key: "contract",
      label: "Sign your contract",
      // Tracked now. This step said "not tracked here" until HCS-11 began issuing the
      // contract and taking the signature on screen — and it is not a separate errand from
      // the documents step below: signing files the signed job-offer form, so it comes off
      // that checklist at the same moment.
      //
      // The People Code still says nothing about signing a contract, which is why the
      // questions in `BeforeYouJoin` are unchanged. Where somebody *is* is now known; what
      // the rules are is still not written down.
      detail: contract
        ? contract.is_signed
          ? `Signed on ${readableDate(contract.signed_on)}`
          : contract.signed_on
            ? "A form on file has not been accepted — sign it here"
            : "Read it and sign — nothing to print"
        : "Issued with your visa application",
      // Current whenever it is unsigned — including while the documents above are still
      // going in, because nothing stops somebody signing first. The order on this board is
      // a recommendation, which is how HCS-11 treats it too: "the order is shown, not
      // enforced". Two steps can be current at once and the heading takes the earlier.
      state: contract?.is_signed ? "done" : "current",
      phase: "before",
      owner: "You",
      counts: true,
      // Opens the same signing panel the home page card opens, by asking for it in
      // the assistant's own words. One way in, not a second one built here.
      ...(contract?.is_signed
        ? {}
        : { action: { label: "Read and sign", prompt: "I want to sign my contract" } }),
    },
    {
      key: "checked",
      label: "Documents checked",
      detail: heldForReview
        ? "We are looking at something on your case"
        : assessed
          ? "Every check passed"
          : "We check them once they are all in",
      // Deliberately separate from the step below. A case whose checks found something
      // sits at "Under Review": checked, and held. Marking this done while the visa step
      // waits is the honest reading — collapsing the two would tell somebody their
      // application had been lodged when it is sitting on a desk.
      state: assessed ? "done" : everythingIn ? "current" : "waiting",
      phase: "processing",
      owner: "HC Services",
      counts: true,
    },
    {
      key: "visa",
      label: "Visa application",
      detail: withThePro
        ? "Lodged on your behalf"
        : "Sent to the PRO once every check has passed",
      state: withThePro ? "done" : "waiting",
      phase: "processing",
      owner: "The PRO",
      counts: true,
    },
    {
      key: "medical",
      label: "Medical examination",
      // As with the contract: no field, no document, no clause. Shown so the journey is
      // not misleading by omission, marked so an absence is not read as a state.
      detail: "Not tracked here — People & Culture will be in touch",
      state: "untracked",
      phase: "processing",
      owner: "People & Culture",
      // Counted, even though nothing here can ever tick it.
      //
      // This was excluded on the reasoning that a step which cannot complete should not
      // hold the figure below a hundred. That had it backwards. The medical is real work
      // that has genuinely not happened, and a ring reading 100% over it tells somebody
      // they are ready to join when the thing standing between them and their first day is
      // still outstanding. Better to be short of a hundred and true.
      counts: true,
    },
    {
      key: "day-one",
      label: "Day 1",
      // The contract's date, not the HR record's, where there is one. They disagree for
      // four of the six joiners, and the contract is the document the employee signs — a
      // page that states one date over a contract stating another is the page that is
      // wrong. The record's date is the fallback for anybody with no contract.
      detail: readableDate(contract?.start_date || startDate) || "To be confirmed",
      state: "waiting",
      phase: "ready",
      owner: "You and your team",
      // A date, not a milestone. Nothing in either system ever flips it.
      counts: false,
    },
  ];
}
