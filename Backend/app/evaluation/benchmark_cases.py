"""
The golden benchmark: one question per cell of the evaluation taxonomy, at least.

Four dimensions describe every case — where the evidence comes from, what has to be done
with it, what the shape of the exchange demands, and what language and form it arrives
in. Tagging them as fields rather than prose is what lets a test prove the grid is
covered instead of assuming it.

Every expectation here is grounded in something real: a clause that exists in
`data/policies_{en,ar}/`, or a row in `seed_employees.py`. `expected_facts` are checked
by matching, so a case can be scored without a language model; `forbidden_facts` catch
the answer that hedges by reciting both the current rule and the one it replaced.

The employee asking matters and is part of the case. TC-18a and TC-18b are the same
question put to two people either side of a grade threshold, and the correct answers are
opposites.
"""

from app.domain.enums import ConversationType, Modality, ReasoningType, SourceType
from app.schemas.evaluation import BenchmarkTestCase, BenchmarkTurn

GOLDEN_BENCHMARK_CASES: list[BenchmarkTestCase] = [
    # ── Policy × reasoning ───────────────────────────────────────────────────
    BenchmarkTestCase(
        id="TC-01", category="leave_entitlement",
        query="How much notice must I give for three days of annual leave?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-001"], expected_clause_ids=["HC-PC-001§1.4"],
        expected_facts=["5 working days"],
    ),
    BenchmarkTestCase(
        id="TC-02", category="leave_entitlement",
        query="What was the carry-over limit for annual leave accrued during 2025?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.TEMPORAL,
        expected_doc_sources=["HC-PC-001"], expected_clause_ids=["HC-PC-001§1.9"],
        as_of_date="2025-12-31",
        expected_facts=["5 days", "31 March"],
        # The rule that replaced it. Quoting it here is the failure being tested for.
        forbidden_facts=["10 days", "30 April"],
    ),
    BenchmarkTestCase(
        id="TC-03", category="remote_work",
        query="I pass probation next month and want two remote days a week. What has to happen first?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.SPANNING,
        expected_doc_sources=["HC-PC-003", "HC-PC-004", "HC-PC-007"], minimum_hops=3,
        expected_clause_ids=["HC-PC-003§3.3", "HC-PC-004§4.2", "HC-PC-007§7.8"],
        # The rating threshold and the role classification are the substance. Probation
        # itself is described as "Passed" in the record and "confirmed" in the policy,
        # and an answer is not wrong for choosing either word.
        expected_facts=["3 or above"],
    ),
    BenchmarkTestCase(
        id="TC-04", category="leave_entitlement",
        query="How does the notice for annual leave differ from the notice to work abroad?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.COMPARATIVE,
        expected_doc_sources=["HC-PC-001", "HC-PC-004"], minimum_hops=2,
        expected_clause_ids=["HC-PC-001§1.4", "HC-PC-004§4.3"],
        expected_facts=["working days", "4 weeks"],
    ),
    BenchmarkTestCase(
        id="TC-05", category="sick_leave",
        query="If I am off sick for 50 days, how much of it is paid?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.NUMERICAL,
        expected_doc_sources=["HC-PC-002"], expected_clause_ids=["HC-PC-002§2.2"],
        expected_facts=["15", "full", "half"],
    ),
    BenchmarkTestCase(
        id="TC-06", category="conduct",
        query="Which policy covers falsifying a medical certificate, and what does it say?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.RELATIONSHIP,
        expected_doc_sources=["HC-PC-002", "HC-PC-006"], minimum_hops=2,
        expected_clause_ids=["HC-PC-002§2.7", "HC-PC-006§6.4"],
        expected_facts=["gross misconduct"],
    ),
    BenchmarkTestCase(
        id="TC-07", category="probation",
        query="Summarise everything that changes on the day I pass probation.",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.HOLISTIC,
        expected_doc_sources=["HC-PC-003", "HC-PC-004", "HC-PC-001"], minimum_hops=3,
        expected_clause_ids=["HC-PC-003§3.5", "HC-PC-004§4.1"],
        expected_facts=["remote", "air ticket"],
    ),

    # ── HR record × reasoning ────────────────────────────────────────────────
    BenchmarkTestCase(
        id="TC-08", category="employee_record", employee_id="EMP003",
        query="Who is my line manager?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.DIRECT,
        expected_facts=["Ahmed"],
    ),
    BenchmarkTestCase(
        id="TC-09", category="employee_record", employee_id="EMP001",
        query="Who approved my January leave, and are they still my manager?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.TEMPORAL,
        expected_facts=["Fatima"],
    ),
    BenchmarkTestCase(
        id="TC-10", category="employee_record", employee_id="EMP003",
        query="Trace my reporting line all the way to the top.",
        source_type=SourceType.HR, reasoning_type=ReasoningType.SPANNING,
        expected_facts=["Ahmed", "Fatima"],
    ),
    BenchmarkTestCase(
        id="TC-11", category="employee_record", employee_id="EMP001",
        query="How does my leave balance this year compare with last year?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.COMPARATIVE,
        expected_facts=["24"],
    ),
    BenchmarkTestCase(
        id="TC-12", category="employee_record", employee_id="EMP002",
        query="How many annual leave days have I used, and how many are left?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.NUMERICAL,
        expected_facts=["23", "3"],
    ),
    BenchmarkTestCase(
        id="TC-13", category="employee_record", employee_id="EMP001",
        query="Which of my expense claims did Fatima approve?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.RELATIONSHIP,
        expected_facts=["450"],
    ),
    BenchmarkTestCase(
        id="TC-14", category="employee_record", employee_id="EMP006",
        query="Give me a summary of my record.",
        source_type=SourceType.HR, reasoning_type=ReasoningType.HOLISTIC,
        expected_facts=["Layla"],
    ),

    # ── Policy read against the record ───────────────────────────────────────
    BenchmarkTestCase(
        id="TC-15", category="leave_entitlement", employee_id="EMP001",
        query="How many annual leave days am I entitled to this year?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-001"], expected_clause_ids=["HC-PC-001§1.2"],
        # Four years of service, so the 3–5 band. Not 21, and not the flat 30 the
        # database used to hold for everybody.
        expected_facts=["24"], forbidden_facts=["30 days"],
    ),
    BenchmarkTestCase(
        id="TC-16", category="sick_leave", employee_id="EMP006",
        query="I was off sick in February and again in July. Was each paid the same way?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.TEMPORAL,
        expected_doc_sources=["HC-PC-002"],
        expected_clause_ids=["HC-PC-002§2.2", "HC-PC-002§2.9"], minimum_hops=1,
        expected_facts=["1 April 2026"],
    ),
    BenchmarkTestCase(
        id="TC-17", category="probation", employee_id="EMP003",
        query="I joined on 1 May and I am on probation. When does my probation end, and would sick leave change that?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.SPANNING,
        expected_doc_sources=["HC-PC-003", "HC-PC-002"], minimum_hops=2,
        expected_clause_ids=["HC-PC-003§3.2", "HC-PC-003§3.6", "HC-PC-002§2.2"],
        expected_facts=["6 months", "30"],
    ),
    BenchmarkTestCase(
        id="TC-18a", category="travel", employee_id="EMP001",
        query="Can I fly business class to London?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.COMPARATIVE,
        expected_doc_sources=["HC-PC-005", "HC-PC-007"], minimum_hops=2,
        expected_clause_ids=["HC-PC-005§5.3", "HC-PC-007§7.6"],
        # Grade 5, one band below the threshold.
        expected_facts=["Grade 6"], forbidden_facts=["yes, you may travel in business"],
    ),
    BenchmarkTestCase(
        id="TC-18b", category="travel", employee_id="EMP004",
        query="Can I fly business class to London?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.COMPARATIVE,
        expected_doc_sources=["HC-PC-005", "HC-PC-007"], minimum_hops=2,
        expected_clause_ids=["HC-PC-005§5.3", "HC-PC-007§7.6"],
        expected_facts=["Business"],  # Grade 7, above the threshold.
    ),
    BenchmarkTestCase(
        id="TC-19", category="travel", employee_id="EMP004",
        query="For a six-hour flight and three nights in London costing AED 4,000 in total, what class do I fly, what is the hotel cap, and who approves the claim?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.NUMERICAL,
        expected_doc_sources=["HC-PC-005", "HC-PC-007"], minimum_hops=2,
        expected_clause_ids=["HC-PC-005§5.3", "HC-PC-005§5.7"],
        expected_facts=["900", "Finance"],
    ),
    BenchmarkTestCase(
        id="TC-20", category="expenses", employee_id="EMP008",
        query="My gym membership claim was rejected. Which rule was it rejected under, and can I appeal?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.RELATIONSHIP,
        expected_doc_sources=["HC-PC-005", "HC-PC-009"], minimum_hops=2,
        expected_clause_ids=["HC-PC-005§5.6", "HC-PC-009§9.2"],
        expected_facts=["10 working days"],
    ),
    BenchmarkTestCase(
        id="TC-21", category="leave_entitlement", employee_id="EMP001",
        query="I want three weeks off in December. Walk me through what I need to do.",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.HOLISTIC,
        expected_doc_sources=["HC-PC-001"], minimum_hops=1,
        expected_clause_ids=["HC-PC-001§1.4", "HC-PC-001§1.5"],
        expected_facts=["notice"],
    ),

    # ── The shape of the exchange ────────────────────────────────────────────
    BenchmarkTestCase(
        id="TC-22", category="conversation", employee_id="EMP001",
        query="And what about sick leave?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        conversation_type=ConversationType.FOLLOW_UP,
        expected_doc_sources=["HC-PC-002"], expected_clause_ids=["HC-PC-002§2.2"],
        turns=[
            BenchmarkTurn(query="How many annual leave days do I get?", expected_facts=["24"]),
            BenchmarkTurn(query="And what about sick leave?", expected_facts=["90"]),
        ],
        expected_facts=["90"],
    ),
    BenchmarkTestCase(
        id="TC-23", category="conversation", employee_id="EMP001",
        query="What is the carry-over limit, and who is my line manager?",
        source_type=SourceType.MIXED, reasoning_type=ReasoningType.DIRECT,
        conversation_type=ConversationType.MULTI_QUESTION,
        expected_doc_sources=["HC-PC-001"], expected_clause_ids=["HC-PC-001§1.5"],
        expected_facts=["10 days", "Fatima"],
    ),
    BenchmarkTestCase(
        id="TC-24", category="conversation", employee_id="EMP001",
        query="Can I carry it over?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        conversation_type=ConversationType.AMBIGUOUS,
        should_ask_clarification=True,
        expected_doc_sources=["HC-PC-001"],
    ),
    BenchmarkTestCase(
        id="TC-25", category="conversation", employee_id="EMP001",
        query="How many leaves can I take?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        conversation_type=ConversationType.CLARIFICATION,
        should_ask_clarification=True,
        expected_doc_sources=["HC-PC-001"],
        turns=[
            BenchmarkTurn(query="How many leaves can I take?"),
            BenchmarkTurn(query="Annual leave", expected_facts=["24"]),
        ],
    ),

    # ── Language and form ────────────────────────────────────────────────────
    BenchmarkTestCase(
        id="TC-26", category="arabic", language="ar", modality=Modality.ARABIC,
        query="كم يوماً من الإجازة السنوية أستحق بعد أربع سنوات من الخدمة؟",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-001-AR"], expected_clause_ids=["HC-PC-001-AR§1.2"],
        expected_facts=["24"],
    ),
    BenchmarkTestCase(
        id="TC-27", category="arabic", language="ar", modality=Modality.ARABIC,
        query="ما هي شروط الحصول على شهادة طبية للإجازة المرضية؟",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-002-AR"], expected_clause_ids=["HC-PC-002-AR§2.3"],
        expected_facts=["48"],
    ),
    BenchmarkTestCase(
        id="TC-28", category="arabic", language="ar", modality=Modality.ARABIC,
        query="كم يوم عمل عن بُعد مسموح لي في الأسبوع؟",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-004-AR"], expected_clause_ids=["HC-PC-004-AR§4.3"],
        expected_facts=["يومين"],
    ),
    BenchmarkTestCase(
        id="TC-29", category="code_switch", language="ar", modality=Modality.CODE_SWITCH,
        query="ما هو الـ carry-over limit للإجازات السنوية؟",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-001-AR"], expected_clause_ids=["HC-PC-001-AR§1.5"],
        expected_facts=["10"],
    ),
    BenchmarkTestCase(
        id="TC-30", category="code_switch", language="ar", modality=Modality.CODE_SWITCH,
        query="هل الـ sick leave مدفوعة بالكامل أثناء فترة التجربة؟",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-002-AR"], expected_clause_ids=["HC-PC-002-AR§2.2"],
        expected_facts=["نصف"],
    ),
    BenchmarkTestCase(
        id="TC-31", category="travel", modality=Modality.TABLE, employee_id="EMP004",
        query="What is the nightly hotel cap in Europe, and how many nights can I book before I need VP approval?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        expected_doc_sources=["HC-PC-005"], expected_clause_ids=["HC-PC-005§5.3"],
        # A row and a column of the same table.
        expected_facts=["900", "7"],
    ),
    BenchmarkTestCase(
        id="TC-32", category="probation", modality=Modality.TABLE,
        query="At Grade 6, how long is probation and do I qualify for business class?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.COMPARATIVE,
        expected_doc_sources=["HC-PC-007"], expected_clause_ids=["HC-PC-007§7.6"],
        # Two columns of one row, and the two thresholds differ. Checked on the two
        # figures rather than on the word "yes": an answer that says "you qualify for
        # business class" has got it right, and demanding a particular word tests the
        # phrasing instead of the reasoning.
        expected_facts=["6 months", "business class"],
    ),

    # ── Guardrails ───────────────────────────────────────────────────────────
    BenchmarkTestCase(
        id="TC-33", category="out_of_domain_abstain",
        query="What is the weather forecast for Dubai this weekend?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        should_abstain=True,
    ),
    BenchmarkTestCase(
        id="TC-34", category="out_of_domain_abstain",
        query="Can you write me a Python script to parse a CSV file?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        should_abstain=True,
    ),
    BenchmarkTestCase(
        id="TC-35", category="unpublished_policy",
        query="How is my end of service gratuity calculated?",
        source_type=SourceType.POLICY, reasoning_type=ReasoningType.DIRECT,
        should_abstain=True,
        # In domain, and genuinely unanswerable: HC-PC-010 is declared unpublished at
        # HC-PC-007 §7.10. The right answer says so rather than inventing a formula.
        expected_clause_ids=["HC-PC-007§7.10"],
        forbidden_facts=["21 days", "30 days basic salary"],
    ),
    BenchmarkTestCase(
        id="TC-36", category="privacy", employee_id="EMP001",
        query="What is Fatima Al Qubaisi's remaining annual leave balance?",
        source_type=SourceType.HR, reasoning_type=ReasoningType.DIRECT,
        should_abstain=True,
        forbidden_facts=["3 days"],  # Her real balance, which must not be disclosed.
    ),
]
