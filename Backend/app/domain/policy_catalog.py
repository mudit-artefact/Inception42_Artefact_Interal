"""
The one place every policy document is described.

Before this module the same documents were listed in five different files, and the lists
had already drifted apart. Everything now reads from here.

The Markdown under `data/policies_{en,ar}/` is the source of truth for content. The PDFs
are rendered from it by `scripts/generate_policy_pdfs.py`, so a citation and the page it
links to say the same thing. They did not always: the PDF text was written by hand,
independently of the Markdown, and the two disagreed on notice periods, certification
thresholds, absence scoring and expense bands.

There is no `diagram_transcription` any more. Each document used to carry a paragraph a
person had typed out from a flowchart image, and those paragraphs were a third version
of the same rules, disagreeing with both the Markdown and the PDF. The processes they
described are now written into the policies themselves — the probation milestone table
at HC-PC-003 §3.3.1 is the probation flowchart, the notice table at HC-PC-001 §1.4.1 is
the leave request flow — so the transcriptions carried no information that the policy did
not already state, and could only contradict it.
"""

from dataclasses import dataclass, field
from typing import Optional

PEOPLE_AND_CULTURE = "People & Culture Division"
FINANCE_AND_PEOPLE = "Finance Division and People & Culture Division"


@dataclass(frozen=True)
class PolicyDocument:
    """One policy document, in one language."""

    code: str
    title: str
    pdf_filename: str
    language: str
    markdown_filename: Optional[str] = None
    owner: str = PEOPLE_AND_CULTURE
    # Retained because the web interface reads this key off /policies and the response
    # shape is a published contract. It no longer marks a diagram: the PDFs are rendered
    # from the Markdown and contain no images. It is the page a reader should open first.
    diagram_page: int = 1
    topics: list[str] = field(default_factory=list)
    topic_key: Optional[str] = None
    quick_link_section: Optional[str] = None

    @property
    def pdf_url(self) -> str:
        """Where the web interface can download this document."""
        return f"/api/v1/hcs01/policies/pdf/{self.pdf_filename}"


POLICY_CATALOG: dict[str, PolicyDocument] = {
    "HC-PC-001": PolicyDocument(
        code="HC-PC-001",
        title="Annual Leave Policy",
        pdf_filename="01_annual_leave_policy.pdf",
        language="en",
        markdown_filename="01_annual_leave.md",
        topics=["Entitlement", "Notice periods", "Carry-over rules", "Public holidays"],
        topic_key="annual",
        quick_link_section="HC-PC-001 Section 1.2",
    ),
    "HC-PC-002": PolicyDocument(
        code="HC-PC-002",
        title="Sick Leave Policy",
        pdf_filename="02_sick_leave_policy.pdf",
        language="en",
        markdown_filename="02_sick_leave.md",
        topics=["Entitlement", "Pay tranches", "Medical certificates", "Bradford Factor"],
        topic_key="sick",
        quick_link_section="HC-PC-002 Section 2.2",
    ),
    "HC-PC-003": PolicyDocument(
        code="HC-PC-003",
        title="Probation Policy",
        pdf_filename="03_probation_policy.pdf",
        language="en",
        markdown_filename="03_probation.md",
        topics=["Duration", "Review milestones", "Extension", "Benefits"],
        topic_key="probation",
        quick_link_section="HC-PC-003 Section 3.3",
    ),
    "HC-PC-004": PolicyDocument(
        code="HC-PC-004",
        title="Remote Work & Flexible Working Policy",
        pdf_filename="04_remote_work_policy.pdf",
        language="en",
        markdown_filename="04_remote_work.md",
        topics=["Eligibility", "Role classes", "Core hours", "Internet allowance"],
        topic_key="remote",
        quick_link_section="HC-PC-004 Section 4.2",
    ),
    "HC-PC-005": PolicyDocument(
        code="HC-PC-005",
        title="Expense Claims & Reimbursement Policy",
        pdf_filename="05_expense_claims_policy.pdf",
        language="en",
        markdown_filename="05_expense_claims.md",
        owner=FINANCE_AND_PEOPLE,
        topics=["Travel", "Per diem", "Hotel caps", "Approval thresholds"],
        topic_key="expenses",
        quick_link_section="HC-PC-005 Section 5.7",
    ),
    "HC-PC-006": PolicyDocument(
        code="HC-PC-006",
        title="Disciplinary Policy",
        pdf_filename="06_disciplinary_policy.pdf",
        language="en",
        markdown_filename="06_disciplinary.md",
        topics=["Unauthorised absence", "Gross misconduct", "Suspension", "Appeals"],
        topic_key="disciplinary",
        quick_link_section="HC-PC-006 Section 6.4",
    ),
    "HC-PC-007": PolicyDocument(
        code="HC-PC-007",
        title="Definitions, Grades & How to Read This Code",
        pdf_filename="07_definitions_policy.pdf",
        language="en",
        markdown_filename="07_definitions.md",
        topics=["Grade bands", "Day definitions", "Continuous service", "Forms register"],
        topic_key="definitions",
        quick_link_section="HC-PC-007 Section 7.6",
    ),
    "HC-PC-008": PolicyDocument(
        code="HC-PC-008",
        title="Capability & Performance Management Policy",
        pdf_filename="08_capability_policy.pdf",
        language="en",
        markdown_filename="08_capability.md",
        topics=["Medical capability", "Performance improvement", "Appeals"],
        topic_key="capability",
        quick_link_section="HC-PC-008 Section 8.2",
    ),
    "HC-PC-009": PolicyDocument(
        code="HC-PC-009",
        title="Grievance & Appeals Policy",
        pdf_filename="09_grievance_policy.pdf",
        language="en",
        markdown_filename="09_grievance.md",
        topics=["Raising a grievance", "Appeals", "Protection from detriment"],
        topic_key="grievance",
        quick_link_section="HC-PC-009 Section 9.2",
    ),
    # ── Arabic editions ──────────────────────────────────────────────────────
    # These now have a Markdown source of their own, so they are indexed from real
    # Arabic text rather than from whatever could be scraped off a PDF page. The three
    # procedural policies (006, 008, 009) are not published in Arabic; that gap is
    # declared, so a question about them can be answered honestly rather than guessed.
    "HC-PC-001-AR": PolicyDocument(
        code="HC-PC-001-AR",
        title="سياسة الإجازات السنوية",
        pdf_filename="01_annual_leave_ar.pdf",
        language="ar",
        markdown_filename="01_annual_leave.md",
        topics=["الاستحقاق", "مهلة الإشعار", "ترحيل الإجازات", "العطل الرسمية"],
        topic_key="annual",
        quick_link_section="HC-PC-001 Section 1.2",
    ),
    "HC-PC-002-AR": PolicyDocument(
        code="HC-PC-002-AR",
        title="سياسة الإجازات المرضية",
        pdf_filename="02_sick_leave_ar.pdf",
        language="ar",
        markdown_filename="02_sick_leave.md",
        topics=["الاستحقاق", "شرائح الأجر", "الشهادات الطبية", "معامل برادفورد"],
        topic_key="sick",
        quick_link_section="HC-PC-002 Section 2.2",
    ),
    "HC-PC-003-AR": PolicyDocument(
        code="HC-PC-003-AR",
        title="سياسة فترة التجربة",
        pdf_filename="03_probation_ar.pdf",
        language="ar",
        markdown_filename="03_probation.md",
        topics=["المدة", "مراحل المراجعة", "التمديد", "المزايا"],
        topic_key="probation",
        quick_link_section="HC-PC-003 Section 3.3",
    ),
    "HC-PC-004-AR": PolicyDocument(
        code="HC-PC-004-AR",
        title="سياسة العمل المرن والعمل عن بُعد",
        pdf_filename="04_remote_work_ar.pdf",
        language="ar",
        markdown_filename="04_remote_work.md",
        topics=["الاستحقاق", "فئات الوظائف", "ساعات العمل", "بدل الإنترنت"],
        topic_key="remote",
        quick_link_section="HC-PC-004 Section 4.2",
    ),
    "HC-PC-005-AR": PolicyDocument(
        code="HC-PC-005-AR",
        title="سياسة المصروفات واستردادها",
        pdf_filename="05_expense_claims_ar.pdf",
        language="ar",
        markdown_filename="05_expense_claims.md",
        owner=FINANCE_AND_PEOPLE,
        topics=["السفر", "البدل اليومي", "حدود الإقامة", "حدود الاعتماد"],
        topic_key="expenses",
        quick_link_section="HC-PC-005 Section 5.7",
    ),
}


def english_documents() -> list[PolicyDocument]:
    """The English editions, in catalogue order. What the web interface lists."""
    return [document for document in POLICY_CATALOG.values() if document.language == "en"]


def title_for(code: str) -> str:
    """A policy's title from its code, falling back to the code itself."""
    document = POLICY_CATALOG.get(code)
    return document.title if document else code
