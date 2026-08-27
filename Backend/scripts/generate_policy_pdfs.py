"""
scripts/generate_policy_pdfs.py
Generates 5 professional PDF policy documents with embedded flowcharts,
decision matrices, and timelines for Multimodal RAG showcase.
"""
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import matplotlib.pyplot as plt

import matplotlib.patches as patches
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DIAGRAMS_DIR = DATA_DIR / "policy_diagrams"
PDFS_DIR = DATA_DIR / "policies_pdf"

DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
PDFS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 1. DIAGRAM GENERATION HELPERS (Using Matplotlib for crisp visual flowcharts)
# ============================================================================

def create_annual_leave_diagram(save_path: Path):
    """Generates the Annual Leave Approval Workflow flowchart diagram."""
    fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")

    # Title
    ax.text(5, 4.6, "Annual Leave Request & Approval Workflow (HC-PC-001)", 
            ha="center", va="center", fontsize=12, fontweight="bold", color="#0f172a")

    # Boxes: Step 1 -> Step 2 -> Step 3 -> Step 4
    steps = [
        ("1. Submit Request", "Employee submits via\nOmni Portal with\nrequired notice period", 1.2, 2.5, "#dbeafe", "#1e40af"),
        ("2. Manager Review", "Line Manager assesses\nteam cover & verifies\navailable balance", 3.7, 2.5, "#fef3c7", "#92400e"),
        ("3. HR Validation", "Automatic check against\nleave caps, carry-over\n& public holidays", 6.2, 2.5, "#e0e7ff", "#3730a3"),
        ("4. Approval & Cal", "System logs approval,\ndeducts balance &\nsyncs Outlook calendar", 8.7, 2.5, "#dcfce7", "#166534"),
    ]

    for title, desc, x, y, bg_col, border_col in steps:
        box = patches.FancyBboxPatch(
            (x - 1.05, y - 1.1), 2.1, 2.2,
            boxstyle="round,pad=0.15,rounding_size=0.2",
            facecolor=bg_col, edgecolor=border_col, linewidth=1.5
        )
        ax.add_patch(box)
        ax.text(x, y + 0.6, title, ha="center", va="center", fontsize=9, fontweight="bold", color=border_col)
        ax.text(x, y - 0.2, desc, ha="center", va="center", fontsize=7.5, color="#334155")

    # Connectors
    for x in [2.35, 4.85, 7.35]:
        ax.annotate("", xy=(x + 0.25, 2.5), xytext=(x - 0.05, 2.5),
                    arrowprops=dict(arrowstyle="->", lw=2, color="#64748b"))

    # Notice Period Footnote
    notice_text = "Notice Rules: 1-2 days leave = 3 days notice | 3-9 days = 10 days notice | 10+ days = 30 days notice"
    ax.text(5, 0.4, notice_text, ha="center", va="center", fontsize=8, fontstyle="italic", color="#475569",
            bbox=dict(boxstyle="square,pad=0.4", facecolor="#f8fafc", edgecolor="#cbd5e1"))

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Generated: {save_path.name}")


def create_sick_leave_diagram(save_path: Path):
    """Generates the Sick Leave Certification & Bradford Factor chart."""
    fig, ax = plt.subplots(figsize=(8.5, 4.4), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    ax.text(5, 4.8, "Sick Leave Certification Decision Tree & Bradford Formula (HC-PC-002)", 
            ha="center", va="center", fontsize=11.5, fontweight="bold", color="#0f172a")

    # Left Box: Days 1-3
    box1 = patches.FancyBboxPatch(
        (0.5, 1.8), 4.0, 2.4,
        boxstyle="round,pad=0.15,rounding_size=0.2",
        facecolor="#fef3c7", edgecolor="#d97706", linewidth=1.5
    )
    ax.add_patch(box1)
    ax.text(2.5, 3.8, "Absence Duration: 1 – 3 Days", ha="center", va="center", fontsize=9.5, fontweight="bold", color="#92400e")
    ax.text(2.5, 3.2, "• Self-Certification permitted\n• Notify supervisor before 09:00 AM\n• Complete Return-to-Work form\n• 100% full basic salary paid", 
            ha="center", va="center", fontsize=8, color="#451a03")

    # Right Box: Days 4+
    box2 = patches.FancyBboxPatch(
        (5.5, 1.8), 4.0, 2.4,
        boxstyle="round,pad=0.15,rounding_size=0.2",
        facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.5
    )
    ax.add_patch(box2)
    ax.text(7.5, 3.8, "Absence Duration: > 3 Consecutive Days", ha="center", va="center", fontsize=9.5, fontweight="bold", color="#991b1b")
    ax.text(7.5, 3.2, "• Mandatory Medical Certificate required\n• Must be from licensed DHA/DOH facility\n• Upload within 48 hours of return\n• Uncertified days treated as unpaid leave", 
            ha="center", va="center", fontsize=8, color="#7f1d1d")

    # Bottom Banner: Bradford Factor Formula
    box3 = patches.FancyBboxPatch(
        (0.5, 0.2), 9.0, 1.2,
        boxstyle="round,pad=0.15,rounding_size=0.15",
        facecolor="#f1f5f9", edgecolor="#64748b", linewidth=1.2
    )
    ax.add_patch(box3)
    ax.text(5, 1.0, "Bradford Factor Score = S² × D   (S = Number of Spells of absence, D = Total Days absent)", 
            ha="center", va="center", fontsize=8.5, fontweight="bold", color="#0f172a")
    ax.text(5, 0.5, "Thresholds: Score < 50: Normal | 51-200: Informal Review | 201-500: Formal Warning | >500: Disciplinary Action", 
            ha="center", va="center", fontsize=7.5, color="#334155")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Generated: {save_path.name}")


def create_probation_diagram(save_path: Path):
    """Generates the Probation Review Milestones Timeline."""
    fig, ax = plt.subplots(figsize=(8.5, 3.8), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    ax.text(5, 3.5, "Probationary Milestones & Performance Review Schedule (HC-PC-003)", 
            ha="center", va="center", fontsize=11.5, fontweight="bold", color="#0f172a")

    # Timeline bar
    ax.plot([1, 9], [1.8, 1.8], color="#94a3b8", lw=4, zorder=1)

    points = [
        (1.5, "Day 1", "Onboarding", "Role objectives\n& mentor assigned", "#3b82f6"),
        (3.8, "Day 30", "First Check-in", "Informal 30-day\nprogress alignment", "#06b6d4"),
        (6.2, "Day 90", "Mid-Probation", "Formal mid-term\nperformance review", "#f59e0b"),
        (8.5, "Day 180", "Confirmation", "Formal sign-off,\nextension or exit", "#10b981"),
    ]

    for x, day, title, desc, col in points:
        ax.scatter([x], [1.8], color=col, s=250, zorder=2, edgecolors="white", linewidths=2)
        ax.text(x, 2.3, f"{day}: {title}", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#0f172a")
        ax.text(x, 1.1, desc, ha="center", va="center", fontsize=7.5, color="#475569")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Generated: {save_path.name}")


def create_remote_work_diagram(save_path: Path):
    """Generates the Remote Work Hybrid Eligibility Matrix."""
    fig, ax = plt.subplots(figsize=(8.5, 4.0), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.5)
    ax.axis("off")

    ax.text(5, 4.1, "Remote & Hybrid Working Eligibility Matrix (HC-PC-004)", 
            ha="center", va="center", fontsize=11.5, fontweight="bold", color="#0f172a")

    categories = [
        ("Office-Based", "1.0 - 2.0 days WFH/wk", "Corporate & Ops Staff (Completed Probation)", "#dbeafe", "#1d4ed8"),
        ("Hybrid Flexible", "Up to 3.0 days WFH/wk", "IT, Strategy & Digital Consultants", "#e0e7ff", "#4338ca"),
        ("Fully Remote", "100% WFH approved", "Designated contractual remote roles only", "#dcfce7", "#15803d"),
        ("Probationary", "Office 5 days/wk", "First 90 days of onboarding", "#fee2e2", "#b91c1c"),
    ]

    for i, (cat, allowance, criteria, bg_col, border_col) in enumerate(categories):
        x = 0.6 + (i * 2.25)
        box = patches.FancyBboxPatch(
            (x, 0.6), 2.1, 3.0,
            boxstyle="round,pad=0.12,rounding_size=0.15",
            facecolor=bg_col, edgecolor=border_col, linewidth=1.5
        )
        ax.add_patch(box)
        ax.text(x + 1.05, 3.1, cat, ha="center", va="center", fontsize=9, fontweight="bold", color=border_col)
        ax.text(x + 1.05, 2.3, allowance, ha="center", va="center", fontsize=8, fontweight="semibold", color="#0f172a")
        ax.text(x + 1.05, 1.4, criteria, ha="center", va="center", fontsize=7.2, color="#334155", wrap=True)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Generated: {save_path.name}")


def create_expense_claims_diagram(save_path: Path):
    """Generates the Expense Claims Threshold & Authorization Matrix."""
    fig, ax = plt.subplots(figsize=(8.5, 4.0), dpi=200)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.5)
    ax.axis("off")

    ax.text(5, 4.1, "Expense Authorization Thresholds & Tiers (HC-PC-005)", 
            ha="center", va="center", fontsize=11.5, fontweight="bold", color="#0f172a")

    tiers = [
        ("Tier 1: Up to AED 500", "Direct Manager Approval", "Local travel, team meals, office sundries.\nReceipt submission within 30 days.", "#f0fdf4", "#15803d"),
        ("Tier 2: AED 501 - 5,000", "Department Head Approval", "Regional travel, client entertainment, equipment.\nPre-approval required.", "#fef3c7", "#b45309"),
        ("Tier 3: AED 5,001 - 25,000", "VP / Finance Director", "International flights, conferences, bulk items.\nPO & quotation required.", "#fee2e2", "#b91c1c"),
        ("Tier 4: > AED 25,000", "CFO & Executive Committee", "Strategic vendor contracts, major travel delegations.", "#f3e8ff", "#7e22ce"),
    ]

    for i, (title, auth, desc, bg_col, border_col) in enumerate(tiers):
        x = 0.5 + (i * 2.3)
        box = patches.FancyBboxPatch(
            (x, 0.5), 2.15, 3.1,
            boxstyle="round,pad=0.12,rounding_size=0.15",
            facecolor=bg_col, edgecolor=border_col, linewidth=1.5
        )
        ax.add_patch(box)
        ax.text(x + 1.07, 3.1, title, ha="center", va="center", fontsize=8.5, fontweight="bold", color=border_col)
        ax.text(x + 1.07, 2.4, auth, ha="center", va="center", fontsize=7.8, fontweight="semibold", color="#0f172a")
        ax.text(x + 1.07, 1.4, desc, ha="center", va="center", fontsize=7.2, color="#334155")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=200)
    plt.close()
    print(f"Generated: {save_path.name}")


# ============================================================================
# 2. PDF DOCUMENT GENERATOR
# ============================================================================

def build_pdf_document(pdf_path: Path, doc_ref: str, title: str, sections: list, diagram_path: Path):
    """Builds a complete, formatted PDF document with embedded diagram."""
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=15,
        spaceAfter=3,
    )

    story = []

    # Header block
    story.append(Paragraph(f"HC SERVICES · PEOPLE CODE POLICY", subtitle_style))
    story.append(Paragraph(f"{title} ({doc_ref})", title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=10))

    # Metadata table
    meta_data = [
        ["Document Ref:", doc_ref, "Version:", "3.2"],
        ["Effective Date:", "1 January 2025", "Owner:", "People & Culture Division"],
        ["Applicability:", "All HC Services Employees", "Classification:", "Internal Company Policy"]
    ]
    meta_table = Table(meta_data, colWidths=[90, 175, 80, 185])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor("#64748b")),
        ('TEXTCOLOR', (2,0), (2,-1), colors.HexColor("#64748b")),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Add sections text
    for sec_title, sec_paragraphs in sections:
        story.append(Paragraph(sec_title, h2_style))
        for p_text in sec_paragraphs:
            if p_text.startswith("•"):
                story.append(Paragraph(p_text, bullet_style))
            else:
                story.append(Paragraph(p_text, body_style))

    # Add embedded Diagram
    if diagram_path.exists():
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Official Process Diagram & Visual Guide", h2_style))
        # Embed diagram image
        rl_img = RLImage(str(diagram_path), width=520, height=255)
        story.append(rl_img)
        story.append(Spacer(1, 10))

    doc.build(story)
    print(f"Generated PDF: {pdf_path.name}")


# ============================================================================
# 3. MAIN POLICY BUILDER
# ============================================================================

def generate_all():
    print("🚀 Generating Policy Diagrams...")
    diag_annual = DIAGRAMS_DIR / "annual_leave_workflow.png"
    diag_sick = DIAGRAMS_DIR / "sick_leave_decision_tree.png"
    diag_probation = DIAGRAMS_DIR / "probation_timeline.png"
    diag_remote = DIAGRAMS_DIR / "remote_work_matrix.png"
    diag_expenses = DIAGRAMS_DIR / "expense_approval_thresholds.png"

    create_annual_leave_diagram(diag_annual)
    create_sick_leave_diagram(diag_sick)
    create_probation_diagram(diag_probation)
    create_remote_work_diagram(diag_remote)
    create_expense_claims_diagram(diag_expenses)

    print("\n📄 Generating PDF Policy Documents...")

    # 1. Annual Leave PDF
    build_pdf_document(
        pdf_path=PDFS_DIR / "01_annual_leave_policy.pdf",
        doc_ref="HC-PC-001",
        title="Annual Leave Policy",
        sections=[
            ("Section 1.1: Purpose & Scope", [
                "This policy defines the annual leave entitlement, accrual rules, request protocols, and carry-over provisions for all full-time and part-time personnel at HC Services.",
            ]),
            ("Section 1.2: Entitlement & Accrual", [
                "• All eligible full-time employees are entitled to 21 to 30 working days of paid annual leave per calendar year (Grade 9+ employees receive 30 working days).",
                "• Annual leave accrues monthly on a pro-rata basis at 1.75 to 2.5 working days per completed month of service.",
                "• Probationary employees accrue leave during their probation period, but taking annual leave is subject to line manager approval.",
            ]),
            ("Section 1.3: Request & Notice Requirements", [
                "• Leave of 1 to 2 days requires a minimum of 3 working days notice.",
                "• Leave of 3 to 9 days requires a minimum of 10 working days notice.",
                "• Leave of 10 or more consecutive days requires a minimum of 30 calendar days notice.",
            ]),
            ("Section 1.4: Carry-Over & Encashment", [
                "• Employees may carry over up to 10 days (or 5 days for standard tier) of unused annual leave into the next calendar year with Line Manager approval.",
                "• Carried-over leave must be utilized before 31 March of the following year, after which unused carried days are forfeited.",
            ]),
        ],
        diagram_path=diag_annual
    )

    # 2. Sick Leave PDF
    build_pdf_document(
        pdf_path=PDFS_DIR / "02_sick_leave_policy.pdf",
        doc_ref="HC-PC-002",
        title="Sick Leave & Medical Certificates Policy",
        sections=[
            ("Section 2.1: Purpose & Scope", [
                "This policy outlines sick leave entitlements, medical certification requirements, and absence management thresholds across all entities.",
            ]),
            ("Section 2.2: Sick Leave Entitlement", [
                "• Employees are entitled to up to 90 calendar days of sick leave per service year: First 15 days at 100% full pay, next 30 days at half pay, and remaining 45 days unpaid.",
            ]),
            ("Section 2.3: Medical Certification Rules", [
                "• Absences of 1 to 3 consecutive days may be self-certified, provided the employee notifies their direct supervisor before 09:00 AM on the first day.",
                "• Absences exceeding 3 consecutive days strictly require a valid medical certificate issued by a licensed medical practitioner (DHA/DOH/MOHAP registered).",
                "• Certificates must be uploaded via the employee self-service portal within 48 hours of returning to work.",
            ]),
            ("Section 2.4: Bradford Factor Absence Management", [
                "• The Bradford Factor (S² × D) is utilized to measure the disruption of frequent short-term unplanned absences.",
                "• Scores exceeding 200 trigger an informal review; scores exceeding 500 trigger formal disciplinary review.",
            ]),
        ],
        diagram_path=diag_sick
    )

    # 3. Probation Policy PDF
    build_pdf_document(
        pdf_path=PDFS_DIR / "03_probation_policy.pdf",
        doc_ref="HC-PC-003",
        title="Probation & Onboarding Policy",
        sections=[
            ("Section 3.1: Duration & Scope", [
                "• Standard probation duration is 6 months (180 calendar days) from the official start date.",
                "• Management reserves the right to confirm successful completion early at 3 months, or extend for up to an additional 3 months in exceptional cases.",
            ]),
            ("Section 3.2: Milestone Reviews", [
                "• Day 30 Check-in: Review onboarding tasks and initial goal alignment.",
                "• Day 90 Mid-Term Review: Formal performance evaluation and feedback session.",
                "• Day 180 Final Review: Formal confirmation of permanent employment status.",
            ]),
        ],
        diagram_path=diag_probation
    )

    # 4. Remote Work Policy PDF
    build_pdf_document(
        pdf_path=PDFS_DIR / "04_remote_work_policy.pdf",
        doc_ref="HC-PC-004",
        title="Flexible & Remote Work Policy",
        sections=[
            ("Section 4.1: Hybrid Working Model", [
                "• Regular full-time employees who have passed probation are eligible for up to 2 days of remote work per week.",
                "• Designated IT and digital engineering roles are eligible for up to 3 days per week.",
                "• Employees on probation must work on-site during their initial 90 days of onboarding.",
            ]),
            ("Section 4.2: Core Hours & Security", [
                "• All personnel must be available during core business hours (09:00 to 15:00 GST).",
                "• Company VPN and multi-factor authentication (MFA) are mandatory on all remote connections.",
            ]),
        ],
        diagram_path=diag_remote
    )

    # 5. Expense Claims Policy PDF
    build_pdf_document(
        pdf_path=PDFS_DIR / "05_expense_claims_policy.pdf",
        doc_ref="HC-PC-005",
        title="Expense Claims & Reimbursement Policy",
        sections=[
            ("Section 5.1: General Guidelines", [
                "• All legitimate, necessary, and reasonable business expenses incurred on company duty are reimbursable.",
                "• Itemized VAT receipts must be submitted via the expense portal within 30 days of occurrence.",
            ]),
            ("Section 5.2: Authorization Thresholds", [
                "• Tier 1 (Up to AED 500): Line Manager approval.",
                "• Tier 2 (AED 501 to AED 5,000): Department Head approval.",
                "• Tier 3 (AED 5,001 to AED 25,000): VP / Finance Director approval.",
                "• Tier 4 (> AED 25,000): CFO and Executive Committee approval.",
            ]),
        ],
        diagram_path=diag_expenses
    )

    print("\n✅ All 5 PDF policy documents and diagrams successfully generated!")


if __name__ == "__main__":
    generate_all()
