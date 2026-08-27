"""
scripts/generate_arabic_policy_pdfs.py
Generates official Arabic HR Policy PDFs for HCS-01 Multilingual Multimodal RAG
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, String, Group, Line

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "policies_pdf"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

PRIMARY = colors.HexColor("#1e3a8a")
SECONDARY = colors.HexColor("#0284c7")
ACCENT = colors.HexColor("#f43f5e")
BG_LIGHT = colors.HexColor("#f8fafc")
BORDER = colors.HexColor("#cbd5e1")
TEXT_DARK = colors.HexColor("#0f172a")

def make_header_footer(canvas, doc, title_ar, doc_ref):
    canvas.saveState()
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, A4[1] - 40, A4[0], 40, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(30, A4[1] - 25, "HC Services — People & Culture Division")
    canvas.drawRightString(A4[0] - 30, A4[1] - 25, f"{title_ar} ({doc_ref})")
    
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(30, 40, A4[0] - 30, 40)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(30, 25, "Confidential — Internal Use Only | HC Services UAE")
    canvas.drawRightString(A4[0] - 30, 25, f"Page {doc.page}")
    canvas.restoreState()

def create_flowchart_drawing():
    d = Drawing(480, 220)
    d.add(Rect(0, 0, 480, 220, fillColor=BG_LIGHT, strokeColor=BORDER, strokeWidth=1, rx=8, ry=8))
    d.add(String(240, 195, "مخطط سير العمل — تقديم واعتماد الإجازة السنوية (Workflow)", fontName="Helvetica-Bold", fontSize=12, textAnchor="middle", fillColor=PRIMARY))
    
    steps = [
        ("1. تقديم الطلب", "بوابة أومني", 20, 100),
        ("2. مراجعة المدير", "التحقق من الرصيد", 140, 100),
        ("3. تدقيق الموارد", "مراجعة السياسات", 260, 100),
        ("4. الاعتماد النهائي", "مزامنة التقويم", 380, 100),
    ]
    for title, desc, x, y in steps:
        d.add(Rect(x, y, 90, 60, fillColor=colors.white, strokeColor=SECONDARY, strokeWidth=1.5, rx=5, ry=5))
        d.add(String(x + 45, y + 38, title, fontName="Helvetica-Bold", fontSize=8, textAnchor="middle", fillColor=PRIMARY))
        d.add(String(x + 45, y + 18, desc, fontName="Helvetica", fontSize=7, textAnchor="middle", fillColor=TEXT_DARK))
    
    for x in [112, 232, 352]:
        d.add(Line(x, 130, x + 24, 130, strokeColor=ACCENT, strokeWidth=2))
        d.add(String(x + 12, 136, "->", fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=ACCENT))
    
    d.add(Rect(20, 25, 440, 45, fillColor=colors.HexColor("#eff6ff"), strokeColor=colors.HexColor("#bfdbfe"), strokeWidth=1, rx=4, ry=4))
    d.add(String(240, 50, "فترات الإشعار المطلوبة مسبقاً:", fontName="Helvetica-Bold", fontSize=9, textAnchor="middle", fillColor=PRIMARY))
    d.add(String(240, 32, "1-2 يوم: 3 أيام إشعار | 3-9 أيام: 10 أيام إشعار | 10+ أيام: 30 يوماً إشعار مسبق", fontName="Helvetica", fontSize=8, textAnchor="middle", fillColor=TEXT_DARK))
    return d

def build_annual_leave_ar():
    pdf_path = os.path.join(OUTPUT_DIR, "01_annual_leave_ar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    h1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=16, textColor=PRIMARY, spaceAfter=8, alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=12, textColor=SECONDARY, spaceBefore=10, spaceAfter=4, alignment=TA_RIGHT)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, textColor=TEXT_DARK, leading=14, spaceAfter=6, alignment=TA_RIGHT)
    
    elements = []
    elements.append(Paragraph("سياسة الإجازات السنوية — شركة إتش سي سيرفيسز", h1))
    elements.append(Paragraph("المرجع: HC-PC-001-AR | الإصدار: 3.2 | تاريخ السريان: 1 يناير 2025", body))
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("1.1 نظرة عامة والهدف", h2))
    elements.append(Paragraph("تحدد هذه السياسة استحقاقات الإجازة السنوية وإجراءات التقديم وقواعد الترحيل لكافة موظفي شركة إتش سي سيرفيسز في دولة الإمارات العربية المتحدة.", body))
    
    elements.append(Paragraph("1.2 استحقاق الإجازة السنوية", h2))
    elements.append(Paragraph("يستحق جميع الموظفين بدوام كامل إجازة سنوية مدفوعة الأجر مدتها 30 يوماً تقويمياً (ما يعادل 21 إلى 22 يوم عمل) عن كل سنة خدمة كاملة. ويتم احتساب الإجازة وتراكمها شهرياً بمعدل 2.5 يوماً لكل شهر ميلادي.", body))
    
    table_data = [
        ["الحد الأقصى للرصيد", "أيام العمل السنوية", "الاستحقاق السنوي", "الفئة الوظيفية"],
        ["45 يوماً", "22 يوم عمل", "30 يوماً", "المستشارون والخبراء"],
        ["40 يوماً", "21 يوم عمل", "30 يوماً", "الموظفون العامون"],
    ]
    t = Table(table_data, colWidths=[110, 110, 110, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))
    
    elements.append(Paragraph("1.3 ترحيل الإجازات (Carry-Over)", h2))
    elements.append(Paragraph("يُسمح للموظف بترحيل ما يصل إلى 5 أيام إجازة سنوية كحد أقصى إلى السنة التقويمية التالية. ويجب استخدام هذه الأيام المرحلة في موعد أقصاه 31 مارس من العام الجديد، وإلا اعتُبرت ملغاة تلقائياً.", body))
    
    elements.append(PageBreak())
    
    elements.append(Paragraph("الصفحة 2: مخطط وإجراءات طلب الإجازة واعتمادها", h1))
    elements.append(Paragraph("توضح الأشكال والمخططات التالية آلية اعتماد الإجازات عبر البوابة الإلكترونية ومسؤوليات المدير المباشر:", body))
    elements.append(Spacer(1, 12))
    elements.append(create_flowchart_drawing())
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("2.1 إشعار طلب الإجازة", h2))
    elements.append(Paragraph("يجب تقديم طلب الإجازة وفق المهل الزمنية الموضحة في المخطط أعلاه لضمان تغطية مهام العمل واستمرارية المشاريع.", body))
    
    def on_page(canvas, doc):
        make_header_footer(canvas, doc, "سياسة الإجازات السنوية", "HC-PC-001-AR")
        
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    print(f"[OK] Generated: {pdf_path}")

def build_sick_leave_ar():
    pdf_path = os.path.join(OUTPUT_DIR, "02_sick_leave_ar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=15, textColor=PRIMARY, spaceAfter=8, alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11, textColor=SECONDARY, spaceBefore=8, spaceAfter=4, alignment=TA_RIGHT)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=TEXT_DARK, leading=13, spaceAfter=6, alignment=TA_RIGHT)
    
    elements = [
        Paragraph("سياسة الإجازات المرضية والشهادات الطبية", h1),
        Paragraph("المرجع: HC-PC-002-AR | الإصدار: 2.4 | تاريخ السريان: 1 يناير 2025", body),
        Spacer(1, 10),
        Paragraph("1.1 الاستحقاق القانوني للإجازة المرضية", h2),
        Paragraph("وفقاً لقانون العمل في دولة الإمارات، يحق للموظف إجازة مرضية تصل إلى 90 يوماً في السنة التعاقدية (15 يوماً بأجر كامل، 30 يوماً بنصف أجر، و45 يوماً بدون أجر) بعد إتمام فترة التجربة بنجاح.", body),
        Spacer(1, 10),
        Paragraph("1.2 اشتراطات الشهادات والتقارير الطبية", h2),
        Paragraph("تتطلب أي إجازة مرضية تتجاوز يومين متتاليين تقديم شهادة طبية معتمدة من هيئة الصحة بدبي (DHA) أو دائرة الصحة بأبوظبي (DOH) أو وزارة الصحة خلال 48 ساعة من الغياب.", body),
    ]
    def on_page(canvas, doc):
        make_header_footer(canvas, doc, "سياسة الإجازات المرضية", "HC-PC-002-AR")
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    print(f"[OK] Generated: {pdf_path}")

def build_probation_ar():
    pdf_path = os.path.join(OUTPUT_DIR, "03_probation_ar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    h1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=15, textColor=PRIMARY, spaceAfter=8, alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11, textColor=SECONDARY, spaceBefore=8, spaceAfter=4, alignment=TA_RIGHT)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=TEXT_DARK, leading=13, spaceAfter=6, alignment=TA_RIGHT)
    elements = [
        Paragraph("سياسة فترة التجربة والتأهيل الوظيفي", h1),
        Paragraph("المرجع: HC-PC-003-AR | تاريخ السريان: 1 يناير 2025", body),
        Spacer(1, 10),
        Paragraph("1.1 مدة فترة التجربة وإجراءات التقييم", h2),
        Paragraph("تحدد فترة التجربة بـ 6 أشهر لجميع الموظفين الجدد. يتم إجراء تقييم مرحلي بعد 90 يوماً وتقييم نهائي بعد 180 يوماً لتثبيت الموظف.", body),
        Paragraph("1.2 فترة الإشعار خلال فترة التجربة", h2),
        Paragraph("في حال رغبة الموظف بالاستقالة خلال فترة التجربة، يجب تقديم إشعار خطي مدته 14 يوماً إذا كان سيغادر الدولة، أو 30 يوماً إذا كان سينتقل لعمل آخر داخل الدولة.", body),
    ]
    def on_page(canvas, doc):
        make_header_footer(canvas, doc, "سياسة فترة التجربة", "HC-PC-003-AR")
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    print(f"[OK] Generated: {pdf_path}")

def build_remote_work_ar():
    pdf_path = os.path.join(OUTPUT_DIR, "04_remote_work_ar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    h1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=15, textColor=PRIMARY, spaceAfter=8, alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11, textColor=SECONDARY, spaceBefore=8, spaceAfter=4, alignment=TA_RIGHT)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=TEXT_DARK, leading=13, spaceAfter=6, alignment=TA_RIGHT)
    elements = [
        Paragraph("سياسة العمل المرن والعمل عن بُعد", h1),
        Paragraph("المرجع: HC-PC-004-AR | تاريخ السريان: 1 يناير 2025", body),
        Spacer(1, 10),
        Paragraph("1.1 الأهلية ونموذج العمل الهجين", h2),
        Paragraph("تسمح الشركة بنموذج عمل هجين يتيح للموظفين العمل عن بُعد لمدة تصل إلى يومين أسبوعياً بعد موافقة المدير المباشر، مع الالتزام بالحضور المكتبي في الأيام المتبقية.", body),
    ]
    def on_page(canvas, doc):
        make_header_footer(canvas, doc, "سياسة العمل عن بُعد", "HC-PC-004-AR")
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    print(f"[OK] Generated: {pdf_path}")

def build_expense_claims_ar():
    pdf_path = os.path.join(OUTPUT_DIR, "05_expense_claims_ar.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=54, bottomMargin=54)
    h1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=15, textColor=PRIMARY, spaceAfter=8, alignment=TA_RIGHT)
    h2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=11, textColor=SECONDARY, spaceBefore=8, spaceAfter=4, alignment=TA_RIGHT)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, textColor=TEXT_DARK, leading=13, spaceAfter=6, alignment=TA_RIGHT)
    elements = [
        Paragraph("سياسة استرداد النفقات ومصروفات العمل", h1),
        Paragraph("المرجع: HC-PC-005-AR | تاريخ السريان: 1 يناير 2025", body),
        Spacer(1, 10),
        Paragraph("1.1 حدود الصرف والموافقات", h2),
        Paragraph("تتطلب النفقات حتى 500 درهم موافقة المدير المباشر، بينما تتطلب النفقات بين 500 و 2500 درهم موافقة رئيس القسم، وما يزيد عن 2500 درهم يتطلب موافقة المدير المالي.", body),
    ]
    def on_page(canvas, doc):
        make_header_footer(canvas, doc, "سياسة استرداد النفقات", "HC-PC-005-AR")
    doc.build(elements, onFirstPage=on_page, onLaterPages=on_page)
    print(f"[OK] Generated: {pdf_path}")

if __name__ == "__main__":
    print("Generating Arabic Policy PDFs...")
    build_annual_leave_ar()
    build_sick_leave_ar()
    build_probation_ar()
    build_remote_work_ar()
    build_expense_claims_ar()
    print("[DONE] All Arabic Policy PDFs successfully created in data/policies_pdf/!")
