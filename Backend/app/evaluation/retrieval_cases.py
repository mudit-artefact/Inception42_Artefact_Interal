"""
One query per indexed clause, written the way an employee would ask.

This measures the search on its own, with no model in the loop. That distinction was
worth building: retrieval failures and generation failures look identical from the outside
and were repeatedly confused for one another — a run of answers reading "I could not
confirm this" was diagnosed as retrieval, then routing, then something else again, on the
strength of spot-checking a handful of queries that happened to work.

**How these are written, and why it matters.** Each query is written from the clause but
deliberately not in the clause's words. "Do my leftover days roll into next year?" rather
than "what is the maximum carry-over of unused annual leave?". The second is the clause
with a question mark on it and retrieves itself; only the first measures anything. A test
keeps that honest by refusing a query that shares a long run of wording with its target.

**Relevance is a set, not a single answer.** Several clauses can legitimately answer one
question, and marking only one correct would score a good result as a miss. Where a
question genuinely needs all of them — the ones the taxonomy calls spanning — that is said
explicitly with `every_clause_required`, because finding one of two and calling it a hit
reports a system better than it is.

The known weakness: these were written by the same hand that scores them, so they are
biased toward phrasings that hand thinks of. The no-shared-wording rule narrows that and
does not close it. A review pass by somebody who fields these questions for a living would
be worth an hour before the numbers are quoted to anyone.
"""

from pydantic import BaseModel, Field

from app.domain.enums import Modality, ReasoningType, SourceType


class RetrievalCase(BaseModel):
    """One question, and the clauses that would answer it."""

    query: str
    relevant_clause_ids: list[str] = Field(min_length=1)
    # True where the answer needs every clause named, not any one of them.
    every_clause_required: bool = False

    source_type: SourceType = SourceType.POLICY
    reasoning_type: ReasoningType = ReasoningType.DIRECT
    modality: Modality = Modality.ENGLISH
    language: str = "en"


def _case(query: str, *clauses: str, **tags) -> RetrievalCase:
    return RetrievalCase(query=query, relevant_clause_ids=list(clauses), **tags)


ENGLISH_CASES: list[RetrievalCase] = [
    # ── HC-PC-001 Annual leave ───────────────────────────────────────────────
    _case("When did the annual leave rules last change, and what changed?",
          "HC-PC-001§1.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Does any of this apply to me if I am still new here?",
          "HC-PC-001§1.1"),
    _case("How much time off do I get in a year?",
          "HC-PC-001§1.2"),
    _case("I started in the middle of the year — how much have I built up so far?",
          "HC-PC-001§1.3", reasoning_type=ReasoningType.NUMERICAL),
    _case("How far ahead do I need to tell my manager before taking time off?",
          "HC-PC-001§1.4", modality=Modality.TABLE),
    _case("Do my leftover days roll into next year?",
          "HC-PC-001§1.5"),
    _case("Am I paid my normal salary while I am away, and can I cash the days in instead?",
          "HC-PC-001§1.6"),
    _case("If a national holiday falls in the middle of my time off, does it count?",
          "HC-PC-001§1.7"),
    _case("What happens if somebody just does not turn up and says nothing?",
          "HC-PC-001§1.8", "HC-PC-006§6.3"),
    _case("What was the limit on rolling days over before the rules changed?",
          "HC-PC-001§1.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── HC-PC-002 Sick leave ─────────────────────────────────────────────────
    _case("Which version of the sick pay rules is in force, and when did it start?",
          "HC-PC-002§2.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Am I covered for time off ill on my very first week?",
          "HC-PC-002§2.1"),
    _case("If I am ill for a long stretch, when does my pay start dropping?",
          "HC-PC-002§2.2", modality=Modality.TABLE),
    _case("Do I need a doctor's note, and by when?",
          "HC-PC-002§2.3"),
    _case("Is there anything I have to do on my first day back after being unwell?",
          "HC-PC-002§2.4"),
    _case("What counts as being off long term, and what happens then?",
          "HC-PC-002§2.5"),
    _case("How many separate absences before somebody starts asking questions?",
          "HC-PC-002§2.6", reasoning_type=ReasoningType.NUMERICAL),
    _case("What happens to someone who fakes being ill?",
          "HC-PC-002§2.7", "HC-PC-006§6.4"),
    _case("How was time off ill paid before the change in April?",
          "HC-PC-002§2.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── HC-PC-003 Probation ──────────────────────────────────────────────────
    _case("Has anything about the trial period for new starters been revised?",
          "HC-PC-003§3.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Does the trial period apply if I moved teams internally?",
          "HC-PC-003§3.1"),
    _case("How long before I am a permanent member of staff?",
          "HC-PC-003§3.2"),
    _case("What check-ins happen while I am still new, and who runs them?",
          "HC-PC-003§3.3", modality=Modality.TABLE),
    _case("How much warning would I get if it did not work out early on?",
          "HC-PC-003§3.4"),
    _case("What am I entitled to before I am made permanent?",
          "HC-PC-003§3.5"),
    _case("Can my trial period be made longer, and by how much?",
          "HC-PC-003§3.6"),
    _case("Can I complain about how my trial period is being handled?",
          "HC-PC-003§3.7", "HC-PC-009§9.2"),

    # ── HC-PC-004 Remote work ────────────────────────────────────────────────
    _case("When were the working-from-home rules last updated?",
          "HC-PC-004§4.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Who is allowed to work away from the office at all?",
          "HC-PC-004§4.1"),
    _case("What do I have to satisfy before I can work from home?",
          "HC-PC-004§4.2", "HC-PC-007§7.7"),
    _case("How many days a week can I be away from the office, and can I go abroad?",
          "HC-PC-004§4.3"),
    _case("What am I expected to do while working from home?",
          "HC-PC-004§4.4"),
    _case("How do I actually apply to work from home, and how long does it take?",
          "HC-PC-004§4.5"),
    _case("Will the company pay towards my broadband, and do they lend me a laptop?",
          "HC-PC-004§4.6"),
    _case("What if somebody keeps not showing up on their office days?",
          "HC-PC-004§4.7", "HC-PC-006§6.5"),
    _case("What was the broadband contribution before it went up?",
          "HC-PC-004§4.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── HC-PC-005 Expenses and travel ────────────────────────────────────────
    _case("Have the sign-off limits for spending changed recently?",
          "HC-PC-005§5.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Who owns the spending rules, and who decides if Finance and HR disagree?",
          "HC-PC-005§5.1", reasoning_type=ReasoningType.RELATIONSHIP),
    _case("Do I need permission before I spend, and how long do I have to put the claim in?",
          "HC-PC-005§5.2"),
    _case("What am I allowed to book for flights and hotels on a work trip?",
          "HC-PC-005§5.3", modality=Modality.TABLE),
    _case("Do I get anything towards meals while I am travelling for work?",
          "HC-PC-005§5.4", modality=Modality.TABLE),
    _case("How much can I spend taking a customer out, and does wine count?",
          "HC-PC-005§5.5"),
    _case("Is my gym membership something the company pays for?",
          "HC-PC-005§5.6"),
    _case("Who has to sign off a large claim before I get my money back?",
          "HC-PC-005§5.7", modality=Modality.TABLE),
    _case("What happens if somebody puts in for something they never actually bought?",
          "HC-PC-005§5.8", "HC-PC-006§6.4"),
    _case("What were the sign-off limits on spending last year?",
          "HC-PC-005§5.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── HC-PC-006 Conduct ────────────────────────────────────────────────────
    _case("When did the conduct rules come into force?",
          "HC-PC-006§6.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("If somebody is trying hard but not coping, is that a conduct matter?",
          "HC-PC-006§6.1", "HC-PC-008§8.1", reasoning_type=ReasoningType.COMPARATIVE),
    _case("Am I paid if I am sent home while something is looked into?",
          "HC-PC-006§6.2"),
    _case("What happens the second and third time somebody goes missing without telling anyone?",
          "HC-PC-006§6.3", modality=Modality.TABLE),
    _case("What could get somebody dismissed on the spot?",
          "HC-PC-006§6.4"),
    _case("What if somebody logs on from a coffee shop with company files open?",
          "HC-PC-006§6.5"),
    _case("If I am disciplined, how long do I have to challenge it?",
          "HC-PC-006§6.6", "HC-PC-009§9.2"),

    # ── HC-PC-007 Definitions and reference tables ───────────────────────────
    _case("What is the latest edition of the definitions document?",
          "HC-PC-007§7.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("If my contract says one thing and the handbook says another, which wins?",
          "HC-PC-007§7.1", reasoning_type=ReasoningType.RELATIONSHIP),
    _case("Does taking a long unpaid break reset how long I have worked here?",
          "HC-PC-007§7.2"),
    _case("Does a weekend count when the handbook gives me a number of days?",
          "HC-PC-007§7.3", modality=Modality.TABLE),
    _case("When the handbook says salary, does that include my allowances?",
          "HC-PC-007§7.4"),
    _case("Is absence counted against the calendar year or the last twelve months?",
          "HC-PC-007§7.5", reasoning_type=ReasoningType.TEMPORAL),
    _case("What does my grade actually get me?",
          "HC-PC-007§7.6", modality=Modality.TABLE),
    _case("Why can some jobs be done from home and others cannot?",
          "HC-PC-007§7.7"),
    _case("What do the numbers in a performance review mean?",
          "HC-PC-007§7.8", modality=Modality.TABLE),
    _case("Which form do I need, and where do I send it?",
          "HC-PC-007§7.9", modality=Modality.TABLE),
    _case("Is there anything the handbook mentions but does not actually cover yet?",
          "HC-PC-007§7.10"),

    # ── HC-PC-008 Capability ─────────────────────────────────────────────────
    _case("How current is the guidance on staff who cannot meet their role?",
          "HC-PC-008§8.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("Is being unable to do the job treated as misconduct?",
          "HC-PC-008§8.1", "HC-PC-006§6.1", reasoning_type=ReasoningType.COMPARATIVE),
    _case("What happens once somebody has used up all their time off ill?",
          "HC-PC-008§8.2", "HC-PC-002§2.5"),
    _case("What follows a poor performance score?",
          "HC-PC-008§8.3", "HC-PC-007§7.8"),
    _case("Can I contest the outcome if I am found not up to the job?",
          "HC-PC-008§8.4", "HC-PC-009§9.2"),

    # ── HC-PC-009 Grievances and appeals ─────────────────────────────────────
    _case("When was the complaints procedure last issued?",
          "HC-PC-009§9.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("What kinds of problems can I formally raise?",
          "HC-PC-009§9.1"),
    _case("How do I raise a complaint, and how quickly will it be heard?",
          "HC-PC-009§9.2"),
    _case("Could speaking up be held against me later?",
          "HC-PC-009§9.3"),

    # ── Questions whose answer genuinely spans more than one document ────────
    _case("I pass my trial period next month and want two days a week at home. "
          "What has to happen first?",
          "HC-PC-003§3.3", "HC-PC-004§4.2", "HC-PC-007§7.7",
          every_clause_required=True, reasoning_type=ReasoningType.SPANNING),
    _case("I am off ill for forty days while still new. What does that do to my "
          "trial period and my pay?",
          "HC-PC-002§2.2", "HC-PC-003§3.6",
          every_clause_required=True, reasoning_type=ReasoningType.SPANNING),
    _case("My claim was turned down. Which rule was it turned down under, and how "
          "do I challenge it?",
          "HC-PC-005§5.6", "HC-PC-009§9.2",
          every_clause_required=True, reasoning_type=ReasoningType.SPANNING),
    _case("I am a grade six on a seven hour flight. What can I book, and what is "
          "the nightly limit?",
          "HC-PC-005§5.3", "HC-PC-007§7.6",
          every_clause_required=True, reasoning_type=ReasoningType.SPANNING,
          modality=Modality.TABLE),
]


# The Arabic editions of the five translated policies. Written as an Arabic speaker would
# ask rather than as a translation of the English query above — an employee asking about
# their own leave says "أستحق", which is the verb, not the noun the clause uses.
ARABIC_CASES: list[RetrievalCase] = [
    # ── الإجازة السنوية ──────────────────────────────────────────────────────
    _case("متى صدر آخر تعديل على سياسة الإجازات السنوية؟",
          "HC-PC-001-AR§1.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("هل تسري هذه السياسة على من لم يُثبَّت بعد؟", "HC-PC-001-AR§1.1"),
    _case("كم يوم إجازة أستحق في السنة؟", "HC-PC-001-AR§1.2"),
    _case("التحقت بالعمل في منتصف السنة، كم تراكم لي حتى الآن؟",
          "HC-PC-001-AR§1.3", reasoning_type=ReasoningType.NUMERICAL),
    _case("قبل كم أخبر مديري إذا أردت إجازة؟", "HC-PC-001-AR§1.4", modality=Modality.TABLE),
    _case("هل تنتقل أيامي المتبقية إلى السنة القادمة؟", "HC-PC-001-AR§1.5"),
    _case("هل أتقاضى راتبي كاملاً أثناء الإجازة، وهل أستطيع صرفها نقداً؟",
          "HC-PC-001-AR§1.6"),
    _case("إذا صادفت عطلة رسمية إجازتي، هل تُحتسب علي؟", "HC-PC-001-AR§1.7"),
    _case("ماذا يحدث لمن يتغيب دون إخطار أحد؟", "HC-PC-001-AR§1.8"),
    _case("كم كان حد الترحيل قبل تغيير القاعدة؟",
          "HC-PC-001-AR§1.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── الإجازة المرضية ──────────────────────────────────────────────────────
    _case("أي إصدار من قواعد الأجر أثناء المرض هو المعمول به الآن؟",
          "HC-PC-002-AR§2.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("هل أنا مشمول إذا مرضت في أسبوعي الأول؟", "HC-PC-002-AR§2.1"),
    _case("إذا طالت فترة مرضي، متى يبدأ راتبي بالنقصان؟",
          "HC-PC-002-AR§2.2", modality=Modality.TABLE),
    _case("هل أحتاج تقريراً من الطبيب، ومتى أقدمه؟", "HC-PC-002-AR§2.3"),
    _case("هل علي فعل شيء في أول يوم بعد عودتي من المرض؟", "HC-PC-002-AR§2.4"),
    _case("ما الذي يُعد غياباً طويلاً وماذا يترتب عليه؟", "HC-PC-002-AR§2.5"),
    _case("كم مرة أتغيب قبل أن تبدأ المراجعة؟",
          "HC-PC-002-AR§2.6", reasoning_type=ReasoningType.NUMERICAL),
    _case("ما عقوبة من يدّعي المرض دون أن يكون مريضاً؟", "HC-PC-002-AR§2.7"),
    _case("كيف كان يُحتسب أجر المرض قبل أبريل؟",
          "HC-PC-002-AR§2.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── فترة التجربة ─────────────────────────────────────────────────────────
    _case("هل طرأ تعديل على قواعد فترة التجربة؟",
          "HC-PC-003-AR§3.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("هل تسري فترة التجربة على من انتقل بين الإدارات؟", "HC-PC-003-AR§3.1"),
    _case("متى أصبح مثبتاً في وظيفتي؟", "HC-PC-003-AR§3.2"),
    _case("ما المراجعات التي تجري علي قبل التثبيت، ومن يجريها؟",
          "HC-PC-003-AR§3.3", modality=Modality.TABLE),
    _case("كم مهلة الإنهاء إن لم تنجح التجربة؟", "HC-PC-003-AR§3.4"),
    _case("ما الذي أستحقه قبل أن أُثبَّت؟", "HC-PC-003-AR§3.5"),
    _case("هل يمكن تمديد فترة تجربتي، وكم؟", "HC-PC-003-AR§3.6"),
    _case("هل أستطيع التظلم من طريقة إدارة فترة تجربتي؟", "HC-PC-003-AR§3.7"),

    # ── العمل عن بُعد ────────────────────────────────────────────────────────
    _case("متى حُدِّثت قواعد العمل من المنزل؟",
          "HC-PC-004-AR§4.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("من يحق له العمل خارج المكتب أصلاً؟", "HC-PC-004-AR§4.1"),
    _case("ما الشروط التي علي استيفاؤها للعمل من البيت؟", "HC-PC-004-AR§4.2"),
    _case("كم يوماً أستطيع العمل من البيت أسبوعياً، وهل يمكنني السفر؟",
          "HC-PC-004-AR§4.3"),
    _case("ما المطلوب مني أثناء عملي من البيت؟", "HC-PC-004-AR§4.4"),
    _case("كيف أتقدم بطلب العمل من البيت وكم يستغرق؟", "HC-PC-004-AR§4.5"),
    _case("هل تساهم الشركة في الإنترنت وتوفر لي جهازاً؟", "HC-PC-004-AR§4.6"),
    _case("ماذا لو تخلف الموظف مراراً عن أيام الحضور؟", "HC-PC-004-AR§4.7"),
    _case("كم كان بدل الإنترنت قبل رفعه؟",
          "HC-PC-004-AR§4.9", reasoning_type=ReasoningType.TEMPORAL),

    # ── المصروفات والسفر ─────────────────────────────────────────────────────
    _case("هل تغيرت حدود اعتماد الصرف مؤخراً؟",
          "HC-PC-005-AR§5.0", reasoning_type=ReasoningType.TEMPORAL),
    _case("من يملك قواعد الصرف ومن يرجَّح رأيه عند الخلاف؟",
          "HC-PC-005-AR§5.1", reasoning_type=ReasoningType.RELATIONSHIP),
    _case("هل أحتاج موافقة قبل الصرف، وكم لدي من وقت لتقديم المطالبة؟",
          "HC-PC-005-AR§5.2"),
    _case("ما الذي يحق لي حجزه من طيران وفنادق في رحلة عمل؟",
          "HC-PC-005-AR§5.3", modality=Modality.TABLE),
    _case("هل لي بدل عن الوجبات أثناء السفر للعمل؟",
          "HC-PC-005-AR§5.4", modality=Modality.TABLE),
    _case("كم أستطيع أن أصرف على استضافة عميل؟", "HC-PC-005-AR§5.5"),
    _case("هل تدفع الشركة اشتراك النادي الرياضي؟", "HC-PC-005-AR§5.6"),
    _case("من يعتمد المطالبة الكبيرة قبل أن أستلم المبلغ؟",
          "HC-PC-005-AR§5.7", modality=Modality.TABLE),
    _case("ما عقوبة من يطالب بمصروف لم يتكبده؟", "HC-PC-005-AR§5.8"),
    _case("كم كانت حدود الاعتماد على الصرف العام الماضي؟",
          "HC-PC-005-AR§5.9", reasoning_type=ReasoningType.TEMPORAL),
]

for _case_ in ARABIC_CASES:
    _case_.language = "ar"
    _case_.modality = (
        Modality.TABLE if _case_.modality == Modality.TABLE else Modality.ARABIC
    )

RETRIEVAL_CASES: list[RetrievalCase] = ENGLISH_CASES + ARABIC_CASES
