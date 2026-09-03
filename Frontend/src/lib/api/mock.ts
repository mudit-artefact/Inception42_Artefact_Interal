import type { ChatResponse, EmployeeProfile, PolicySource } from "./types";

export interface MockPersona extends EmployeeProfile {
  policyLinks: PolicySource[];
}

const POL_ANNUAL: PolicySource = { id: "pol-annual", title: "Annual Leave Policy", section: "HR-POL-014 Section 3", url: "#" };
const POL_SICK: PolicySource = { id: "pol-sick", title: "Sick Leave & Medical Certificates", section: "HR-POL-021 Section 2.4", url: "#" };
const POL_REMOTE: PolicySource = { id: "pol-remote", title: "Flexible & Remote Working", section: "HR-POL-036 Section 1", url: "#" };
const POL_TRAVEL: PolicySource = { id: "pol-travel", title: "Travel & Per Diem Guidelines", section: "FIN-POL-009 Section 5", url: "#" };
const POL_PROBATION: PolicySource = { id: "pol-probation", title: "Probation & Onboarding Guide", section: "HR-POL-002 Section 4", url: "#" };
const POL_ACCRUAL: PolicySource = { id: "pol-accrual", title: "Leave Accrual During Probation", section: "HR-POL-014 Section 3.5", url: "#" };
const POL_APPROVALS: PolicySource = { id: "pol-approvals", title: "Manager Leave Approval Duties", section: "HR-PRO-011 Section 2", url: "#" };
const POL_DELEGATION: PolicySource = { id: "pol-delegation", title: "Delegation of Authority", section: "GOV-POL-003 Section 1.2", url: "#" };
const POL_SHIFT: PolicySource = { id: "pol-shift", title: "Clinical Shift & Rota Policy", section: "CLIN-POL-018 Section 2", url: "#" };
const POL_PARTTIME: PolicySource = { id: "pol-parttime", title: "Part-Time & Pro-Rata Entitlements", section: "HR-POL-014 Section 8", url: "#" };

export const MOCK_EMPLOYEES: MockPersona[] = [
  {
    id: "EMP001",
    user_id: "EMP001",
    name: "Alia Al Suwaidi",
    name_ar: "علياء السويدي",
    jobTitle: "Senior Consultant",
    department: "Strategy & Transformation",
    grade: "Grade 8",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 15,
    sick_leave_balance: 5,
    carry_over_days: 3,
    probation_status: "Passed",
    years_of_service: 5,
    email: "alia.suwaidi@hcservices.ae",
    start_date: "2021-03-14",
    balances: [
      { type: "Annual leave", used: 12, entitled: 24, remaining: 15, carry_over: 3, year: 2026, unit: "days" },
      { type: "Sick leave", used: 10, entitled: 15, remaining: 5, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 3, remaining: 3, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_REMOTE, POL_TRAVEL],
  },
  {
    id: "EMP002",
    user_id: "EMP002",
    name: "Rashid Al Ketbi",
    name_ar: "راشد الكتبي",
    jobTitle: "VP, Strategy & Operations",
    department: "Strategy & Transformation",
    grade: "Grade 7",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 23,
    sick_leave_balance: 12,
    carry_over_days: 5,
    probation_status: "Passed",
    years_of_service: 4,
    email: "rashid.ketbi@hcservices.ae",
    start_date: "2022-07-01",
    balances: [
      { type: "Annual leave", used: 6, entitled: 24, remaining: 23, carry_over: 5, year: 2026, unit: "days" },
      { type: "Sick leave", used: 3, entitled: 15, remaining: 12, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 5, remaining: 5, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_APPROVALS, POL_DELEGATION, POL_ANNUAL, POL_TRAVEL],
  },
  {
    id: "EMP003",
    user_id: "EMP003",
    name: "Maitha Al Mazrouei",
    name_ar: "ميثاء المزروعي",
    jobTitle: "Executive Director",
    department: "Executive Leadership",
    grade: "Grade 9",
    manager: "Board of Directors",
    annual_leave_balance: 11,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 7,
    email: "maitha.mazrouei@hcservices.ae",
    start_date: "2019-11-10",
    balances: [
      { type: "Annual leave", used: 15, entitled: 26, remaining: 11, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_APPROVALS, POL_DELEGATION, POL_ANNUAL, POL_REMOTE],
  },
  {
    id: "EMP004",
    user_id: "EMP004",
    name: "Daniel Reed",
    name_ar: "دانيال ريد",
    jobTitle: "Director, Finance & Treasury",
    department: "Finance & Accounting",
    grade: "Grade 6",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 15,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 2,
    email: "daniel.reed@hcservices.ae",
    start_date: "2024-01-22",
    balances: [
      { type: "Annual leave", used: 6, entitled: 21, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_TRAVEL, POL_ANNUAL, POL_REMOTE, POL_APPROVALS],
  },
  {
    id: "EMP005",
    user_id: "EMP005",
    name: "Noura Al Zaabi",
    name_ar: "نورة الزعابي",
    jobTitle: "Senior Specialist (On Leave)",
    department: "Legal & Compliance",
    grade: "Grade 7",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 26,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 6,
    email: "noura.zaabi@hcservices.ae",
    start_date: "2020-09-06",
    balances: [
      { type: "Annual leave", used: 0, entitled: 26, remaining: 26, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_REMOTE],
  },
  {
    id: "EMP006",
    user_id: "EMP006",
    name: "Sultan Al Neyadi",
    name_ar: "سلطان النيادي",
    jobTitle: "Manager, Client Delivery",
    department: "Client Delivery",
    grade: "Grade 8",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 18,
    sick_leave_balance: 56,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 8,
    email: "sultan.neyadi@hcservices.ae",
    start_date: "2018-05-17",
    balances: [
      { type: "Annual leave", used: 8, entitled: 26, remaining: 18, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 34, entitled: 90, remaining: 56, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_APPROVALS],
  },
  {
    id: "EMP007",
    user_id: "EMP007",
    name: "Shamma Al Muhairi",
    name_ar: "شما المهيري",
    jobTitle: "Facilities Supervisor (Probation)",
    department: "Workplace & Facilities",
    grade: "Grade 5",
    manager: "Daniel Reed",
    annual_leave_balance: 10,
    sick_leave_balance: 13,
    carry_over_days: 0,
    probation_status: "Active",
    years_of_service: 1,
    email: "shamma.muhairi@hcservices.ae",
    start_date: "2025-02-03",
    balances: [
      { type: "Annual leave", used: 4, entitled: 14, remaining: 10, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 2, entitled: 15, remaining: 13, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_PROBATION, POL_PARTTIME, POL_SHIFT],
  },
  {
    id: "EMP008",
    user_id: "EMP008",
    name: "Tariq Al Balushi",
    name_ar: "طارق البلوشي",
    jobTitle: "Senior Strategy Specialist",
    department: "Strategy & Transformation",
    grade: "Grade 7",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 21,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 9,
    email: "tariq.balushi@hcservices.ae",
    start_date: "2017-08-20",
    balances: [
      { type: "Annual leave", used: 5, entitled: 26, remaining: 21, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_TRAVEL],
  },
  {
    id: "EMP009",
    user_id: "EMP009",
    name: "Elena Costa",
    name_ar: "إيلينا كوستا",
    jobTitle: "VP, People & Culture",
    department: "People & Culture",
    grade: "Grade 9",
    manager: "Maitha Al Mazrouei",
    annual_leave_balance: 17,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 3,
    email: "elena.costa@hcservices.ae",
    start_date: "2023-04-12",
    balances: [
      { type: "Annual leave", used: 7, entitled: 24, remaining: 17, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_APPROVALS, POL_DELEGATION, POL_ANNUAL],
  },
  {
    id: "EMP010",
    user_id: "EMP010",
    name: "Khalifa Al Dhaheri",
    name_ar: "خليفة الظاهري",
    jobTitle: "Associate Consultant",
    department: "Digital & Technology",
    grade: "Grade 6",
    manager: "Alia Al Suwaidi",
    annual_leave_balance: 16,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 2,
    email: "khalifa.dhaheri@hcservices.ae",
    start_date: "2024-09-15",
    balances: [
      { type: "Annual leave", used: 5, entitled: 21, remaining: 16, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_REMOTE],
  },
  {
    id: "EMP011",
    user_id: "EMP011",
    name: "Hessa Al Shamsi",
    name_ar: "حصة الشامسي",
    jobTitle: "Lead Consultant",
    department: "Strategy & Transformation",
    grade: "Grade 8",
    manager: "Alia Al Suwaidi",
    annual_leave_balance: 16,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 6,
    email: "hessa.shamsi@hcservices.ae",
    start_date: "2020-01-05",
    balances: [
      { type: "Annual leave", used: 10, entitled: 26, remaining: 16, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_TRAVEL],
  },
  {
    id: "EMP012",
    user_id: "EMP012",
    name: "Mohammed Al Marri",
    name_ar: "محمد المري",
    jobTitle: "Associate Analyst",
    department: "Digital & Technology",
    grade: "Grade 5",
    manager: "Alia Al Suwaidi",
    annual_leave_balance: 18,
    sick_leave_balance: 15,
    carry_over_days: 0,
    probation_status: "Passed",
    years_of_service: 1,
    email: "mohammed.marri@hcservices.ae",
    start_date: "2025-06-16",
    balances: [
      { type: "Annual leave", used: 3, entitled: 21, remaining: 18, carry_over: 0, year: 2026, unit: "days" },
      { type: "Sick leave", used: 0, entitled: 15, remaining: 15, carry_over: 0, year: 2026, unit: "days" },
      { type: "Carry-over", used: 0, entitled: 0, remaining: 0, carry_over: 0, year: 2026, unit: "days" },
    ],
    policyLinks: [POL_ANNUAL, POL_SICK, POL_REMOTE],
  },
];

export const MOCK_EMPLOYEE: MockPersona = MOCK_EMPLOYEES[0]!;

export function getMockEmployee(id: string | null | undefined): MockPersona {
  return MOCK_EMPLOYEES.find((e) => e.id === id || e.user_id === id) ?? MOCK_EMPLOYEE;
}

export const POLICY_LINKS: PolicySource[] = MOCK_EMPLOYEE.policyLinks;

export const SUGGESTED_QUESTIONS: string[] = [
  "Has my leave request been approved?",
  "How do I apply for annual leave?",
  "How many annual leave days do I have left?",
  "Can I carry over unused leave into next year?",
];


const MOCK_ANSWERS: { match: RegExp; answer: string; sources: PolicySource[] }[] = [
  {
    match: /has my leave( request)? been approved|is my leave approved|requested leaves|does my leaves? approved|status of my leave/i,
    answer:
      "🎉 **Yes! Your Leave Request has been Approved!**\n\n" +
      "Your annual leave request was reviewed and approved by your manager, **Fatima Maryam Al Qubaisi**.\n\n" +
      "You can add this leave to your calendar (.ics) or email your manager & HR in CC.",
    sources: [
      { title: "Annual Leave Policy", section: "HR-POL-014 Section 4", url: "#", snippet: "Approved leave is officially logged in Omni HR.", score: 0.98 },
    ],
  },
  {
    match: /what leave requests do i need to approve|leave requests? to approve|need to approve/i,
    answer:
      "📋 **Pending Leave Requests Awaiting Your Approval:**\n\n" +
      "• **Request #18** by **Sara Nasser** (Consultant, Strategy): 10 days of Annual Leave from 2026-10-05 to 2026-10-16\n\n" +
      "You can review and click **Approve Leave** or **Reject** on the card, or state the request ID.",
    sources: [
      { title: "Manager Leave Approval Duties", section: "HR-PRO-011 Section 2", url: "#", snippet: "Line managers must review leave requests within 3 working days.", score: 0.95 },
    ],
  },
  {
    match: /carry|carry-over|rollover/i,
    answer:
      "**Yes — up to 10 days** of unused annual leave can be carried into the next calendar year.\n\n" +
      "- Carry-over must be approved by your line manager before **31 December**.\n" +
      "- Carried days expire on **31 March** of the following year.\n" +
      "- Balances above 10 days are forfeited unless a business-critical deferral is approved by HR.",
    sources: [
      { title: "Annual Leave Policy", section: "HR-POL-014 Section 6.2 Carry-over", url: "#", snippet: "Employees may carry forward a maximum of ten (10) working days…", score: 0.94 },
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
      { title: "Sick Leave & Medical Certificates", section: "HR-POL-021 Section 2.4", url: "#", snippet: "Certification is mandatory for absences exceeding three consecutive days…", score: 0.96 },
      { title: "Absence Notification Procedure", section: "HR-PRO-007 Section 1.1", url: "#", snippet: "Notification must be made to the direct supervisor before 09:00…", score: 0.78 },
    ],
  },
  {
    match: /notice|request|apply/i,
    answer:
      "Annual leave should be requested through the HR portal with the following notice:\n\n" +
      "| Duration | Minimum notice |\n| --- | --- |\n| 1–2 days | 3 working days |\n| 3–9 days | 10 working days |\n| 10+ days | 30 calendar days |\n\n" +
      "Requests are approved by your line manager within 5 working days; unanswered requests escalate automatically to the department head.",
    sources: [
      { title: "Annual Leave Policy", section: "HR-POL-014 Section 4 Request & Approval", url: "#", snippet: "Notice requirements scale with the duration of leave requested…", score: 0.93 },
    ],
  },
];

const BALANCE_MATCH = /balance|days left|remaining|how many/i;

function balanceAnswer(employee: MockPersona): { answer: string; sources: PolicySource[] } {
  const lines = employee.balances
    .map((b) => `- **${b.type}:** ${b.remaining} of ${b.entitled + b.carry_over} ${b.unit} remaining`)
    .join("\n");

  return {
    answer:
      `Here is your current entitlement, ${employee.name.split(" ")[0]} (${employee.grade}, ${employee.department}):\n\n` +
      `${lines}\n\n` +
      "Pending requests are not deducted until approved, and public holidays falling inside an approved leave period are not counted against your balance.",
    sources: [
      {
        title: "Annual Leave Policy",
        section: "HR-POL-014 Section 3 Entitlement",
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
