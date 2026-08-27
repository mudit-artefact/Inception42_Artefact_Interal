import type { ChatResponse, EmployeeProfile, PolicySource } from "./types";

export interface MockPersona extends EmployeeProfile {
  policyLinks: PolicySource[];
}

const POL_ANNUAL: PolicySource = { id: "pol-annual", title: "Annual Leave Policy", section: "HR-POL-014 §3", url: "#" };
const POL_SICK: PolicySource = { id: "pol-sick", title: "Sick Leave & Medical Certificates", section: "HR-POL-021 §2.4", url: "#" };
const POL_REMOTE: PolicySource = { id: "pol-remote", title: "Flexible & Remote Working", section: "HR-POL-036 §1", url: "#" };
const POL_TRAVEL: PolicySource = { id: "pol-travel", title: "Travel & Per Diem Guidelines", section: "FIN-POL-009 §5", url: "#" };
const POL_PROBATION: PolicySource = { id: "pol-probation", title: "Probation & Onboarding Guide", section: "HR-POL-002 §4", url: "#" };
const POL_ACCRUAL: PolicySource = { id: "pol-accrual", title: "Leave Accrual During Probation", section: "HR-POL-014 §3.5", url: "#" };
const POL_APPROVALS: PolicySource = { id: "pol-approvals", title: "Manager Leave Approval Duties", section: "HR-PRO-011 §2", url: "#" };
const POL_DELEGATION: PolicySource = { id: "pol-delegation", title: "Delegation of Authority", section: "GOV-POL-003 §1.2", url: "#" };
const POL_SHIFT: PolicySource = { id: "pol-shift", title: "Clinical Shift & Rota Policy", section: "CLIN-POL-018 §2", url: "#" };
const POL_PARTTIME: PolicySource = { id: "pol-parttime", title: "Part-Time & Pro-Rata Entitlements", section: "HR-POL-014 §8", url: "#" };

export const MOCK_EMPLOYEES: MockPersona[] = [
  {
    id: "HCS-01-48213",
    name: "Mohammad Mohsen",
    jobTitle: "Senior Systems Analyst",
    department: "Health Corporate Services — IT",
    grade: "Grade 9",
    manager: "Aisha Al-Kuwari",
    balances: [
      { type: "Annual leave", used: 12, entitled: 30, unit: "days" },
      { type: "Sick leave", used: 3, entitled: 14, unit: "days" },
      { type: "Compassionate", used: 0, entitled: 5, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_REMOTE, POL_TRAVEL],
  },
  {
    id: "HCS-01-51944",
    name: "Layla Haddad",
    jobTitle: "Procurement Officer (Probation)",
    department: "Health Corporate Services — Supply Chain",
    grade: "Grade 6",
    manager: "Omar Al-Sulaiti",
    balances: [
      { type: "Annual leave", used: 1, entitled: 7, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 5, unit: "days" },
      { type: "Compassionate", used: 0, entitled: 3, unit: "days" },
    ],
    policyLinks: [POL_PROBATION, POL_ACCRUAL, POL_ANNUAL, POL_SICK],
  },
  {
    id: "HCS-01-30117",
    name: "Aisha Al-Kuwari",
    jobTitle: "Head of Corporate Systems",
    department: "Health Corporate Services — IT",
    grade: "Grade 13",
    manager: "Dr. Hassan Al-Emadi",
    balances: [
      { type: "Annual leave", used: 18, entitled: 40, unit: "days" },
      { type: "Sick leave", used: 2, entitled: 14, unit: "days" },
      { type: "Study leave", used: 4, entitled: 10, unit: "days" },
    ],
    policyLinks: [POL_APPROVALS, POL_DELEGATION, POL_ANNUAL, POL_TRAVEL],
  },
  {
    id: "HCS-01-62880",
    name: "Noor Rahman",
    jobTitle: "Clinical Coordinator (Part-Time, 0.6 FTE)",
    department: "Health Corporate Services — Clinical Ops",
    grade: "Grade 8",
    manager: "Fatima Al-Naimi",
    balances: [
      { type: "Annual leave", used: 40, entitled: 132, unit: "hours" },
      { type: "Sick leave", used: 8, entitled: 60, unit: "hours" },
      { type: "Compassionate", used: 0, entitled: 24, unit: "hours" },
    ],
    policyLinks: [POL_PARTTIME, POL_SHIFT, POL_ANNUAL, POL_SICK],
  },
];

export const MOCK_EMPLOYEE: MockPersona = MOCK_EMPLOYEES[0]!;

export function getMockEmployee(id: string | null | undefined): MockPersona {
  return MOCK_EMPLOYEES.find((e) => e.id === id) ?? MOCK_EMPLOYEE;
}

export const POLICY_LINKS: PolicySource[] = MOCK_EMPLOYEE.policyLinks;

export const SUGGESTED_QUESTIONS: string[] = [
  "How many annual leave days do I have left this year?",
  "What is the notice period for requesting annual leave?",
  "Can I carry over unused leave into next year?",
  "What documents do I need for sick leave over 3 days?",
  "How does leave accrue during probation?",
];

const MOCK_ANSWERS: { match: RegExp; answer: string; sources: PolicySource[] }[] = [
  {
    match: /carry|carry-over|rollover/i,
    answer:
      "**Yes — up to 10 days** of unused annual leave can be carried into the next calendar year.\n\n" +
      "- Carry-over must be approved by your line manager before **31 December**.\n" +
      "- Carried days expire on **31 March** of the following year.\n" +
      "- Balances above 10 days are forfeited unless a business-critical deferral is approved by HR.",
    sources: [
      { title: "Annual Leave Policy", section: "HR-POL-014 §6.2 Carry-over", url: "#", snippet: "Employees may carry forward a maximum of ten (10) working days…", score: 0.94 },
      { title: "Year-End HR Operations Circular", section: "CIRC-2026-04", url: "#", snippet: "Carry-over requests close on 31 December…", score: 0.81 },
    ],
  },
  {
    match: /sick|medical|certificate/i,
    answer:
      "For sick leave of **more than 3 consecutive days** you must submit:\n\n" +
      "1. A medical certificate from a licensed practitioner, uploaded within 48 hours of returning.\n" +
      "2. A completed **Absence Notification Form** acknowledged by your line manager.\n\n" +
      "Absences of 1–3 days are self-certified but still require same-day notification before 09:00.",
    sources: [
      { title: "Sick Leave & Medical Certificates", section: "HR-POL-021 §2.4", url: "#", snippet: "Certification is mandatory for absences exceeding three consecutive days…", score: 0.96 },
      { title: "Absence Notification Procedure", section: "HR-PRO-007 §1.1", url: "#", snippet: "Notification must be made to the direct supervisor before 09:00…", score: 0.78 },
    ],
  },
  {
    match: /notice|request|apply/i,
    answer:
      "Annual leave should be requested through the HR portal with the following notice:\n\n" +
      "| Duration | Minimum notice |\n| --- | --- |\n| 1–2 days | 3 working days |\n| 3–9 days | 10 working days |\n| 10+ days | 30 calendar days |\n\n" +
      "Requests are approved by your line manager within 5 working days; unanswered requests escalate automatically to the department head.",
    sources: [
      { title: "Annual Leave Policy", section: "HR-POL-014 §4 Request & Approval", url: "#", snippet: "Notice requirements scale with the duration of leave requested…", score: 0.93 },
    ],
  },
];

const BALANCE_MATCH = /balance|days left|remaining|how many/i;

function balanceAnswer(employee: MockPersona): { answer: string; sources: PolicySource[] } {
  const lines = employee.balances
    .map((b) => `- **${b.type}:** ${b.entitled - b.used} of ${b.entitled} ${b.unit} remaining`)
    .join("\n");

  return {
    answer:
      `Here is your current entitlement, ${employee.name.split(" ")[0]} (${employee.grade}, ${employee.department}):\n\n` +
      `${lines}\n\n` +
      "Pending requests are not deducted until approved, and public holidays falling inside an approved leave period are not counted against your balance.",
    sources: [
      {
        title: "Annual Leave Policy",
        section: "HR-POL-014 §3 Entitlement",
        url: "#",
        snippet: `${employee.grade} employees accrue entitlement pro-rata for each completed month of service…`,
        score: 0.91,
      },
      ...employee.policyLinks.slice(0, 1).map((p) => ({ ...p, snippet: "Applies to your employment category.", score: 0.72 })),
    ],
  };
}

const FALLBACK: { answer: string; sources: PolicySource[] } = {
  answer:
    "Here's what the HCS-01 policy library says at a high level. I couldn't find an exact clause for that wording, so please confirm with HR Services before acting on it.\n\n" +
    "You can rephrase your question, or pick one of the suggested questions to see a fully cited answer.",
  sources: [
    { title: "HCS-01 Policy Library — Index", section: "Overview", url: "#", snippet: "Master index of HR, finance and operational policies.", score: 0.42 },
  ],
};

export async function mockChat(
  message: string,
  conversationId: string | null,
  employeeId?: string | null,
): Promise<ChatResponse> {
  await new Promise((r) => setTimeout(r, 900 + Math.random() * 700));

  if (/\bfail\b|\berror\b/i.test(message)) {
    throw new Error("Mock service failure — the concierge could not be reached.");
  }

  const employee = getMockEmployee(employeeId);
  const hit = BALANCE_MATCH.test(message)
    ? balanceAnswer(employee)
    : (MOCK_ANSWERS.find((a) => a.match.test(message)) ?? FALLBACK);

  return {
    answer: hit.answer,
    sources: hit.sources,
    conversation_id: conversationId ?? `mock-${Date.now().toString(36)}`,
  };
}
