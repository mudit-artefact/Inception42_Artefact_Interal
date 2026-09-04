"""
The fixed vocabularies the workflow uses.

These replace three overlapping sets of intent strings that added up to eleven possible
values. One set came from the live classifier, another from a retired rule-based
classifier, and "unknown" was invented by the orchestrator. The response model's default
came from the retired set, so a field could carry a value nothing else understood.
"""

from enum import StrEnum


class QuestionIntent(StrEnum):
    """What the employee is trying to do."""

    GREETING = "greeting"
    HR_QUESTION = "hr_question"
    OUT_OF_SCOPE = "out_of_scope"
    # A request to change the form of the last reply — shorter, simpler, translated —
    # rather than a question about HR. The answer already exists; searching the policy
    # documents for "make that shorter" finds nothing and means nothing.
    ABOUT_THE_LAST_ANSWER = "about_the_last_answer"
    # Actionable transactional leave requests
    APPLY_LEAVE = "apply_leave"
    CANCEL_LEAVE = "cancel_leave"
    CHECK_LEAVE_STATUS = "check_leave_status"
    APPROVE_LEAVE = "approve_leave"
    REJECT_LEAVE = "reject_leave"
    # HCS-11 Proof of Schooling & Education Allowance intents
    CHECK_SCHOOL_VERIFICATION = "check_school_verification"
    SUBMIT_SCHOOL_VERIFICATION = "submit_school_verification"
    REVIEW_SCHOOL_CASES = "review_school_cases"
    DOCUMENT_UPLOAD = "document_upload"



class RequiredEvidence(StrEnum):
    """What a question has to be answered from."""

    POLICY = "policy"
    HR_DATA = "hr_data"
    BOTH = "both"
    UNSUPPORTED = "unsupported"


class AnswerStatus(StrEnum):
    """How a turn finished."""

    VERIFIED = "verified"
    # Some parts of the question were answered and others had nothing behind them.
    PARTIAL = "partial"
    CLARIFICATION_REQUESTED = "clarification_requested"
    REFUSED = "refused"
    SAFE_FALLBACK = "safe_fallback"
    # Action lifecycle statuses
    ACTION_CONFIRMATION_REQUIRED = "action_confirmation_required"
    ACTION_EXECUTED = "action_executed"
    ACTION_REJECTED = "action_rejected"


class FallbackReason(StrEnum):
    """Why the assistant declined to give a direct answer."""

    OUT_OF_SCOPE = "out_of_scope"
    NO_EVIDENCE = "no_evidence"
    UNSUPPORTED_CLAIMS = "unsupported_claims"
    NEEDS_HUMAN = "needs_human"
    # Asked to rework a reply before there was one to rework.
    NOTHING_TO_REPHRASE = "nothing_to_rephrase"


class HrDataField(StrEnum):
    """
    The employee facts the assistant is allowed to read.

    This list is the authorisation boundary. The router names the fields it needs and
    anything outside this list is discarded before the data is read, so the model cannot
    ask for a database column, a table, or another employee's record. It is what replaced
    the endpoint that ran caller-supplied SQL.
    """

    ANNUAL_LEAVE_BALANCE = "annual_leave_balance"
    SICK_LEAVE_BALANCE = "sick_leave_balance"
    CARRY_OVER_DAYS = "carry_over_days"
    LINE_MANAGER = "line_manager"
    MANAGER_HISTORY = "manager_history"
    PROBATION_STATUS = "probation_status"
    YEARS_OF_SERVICE = "years_of_service"
    RECENT_LEAVE_REQUESTS = "recent_leave_requests"
    RECENT_EXPENSE_CLAIMS = "recent_expense_claims"
    EMPLOYEE_PROFILE = "employee_profile"


# ── The evaluation taxonomy ──────────────────────────────────────────────────
# Four independent dimensions a benchmark question is described by. They live here with
# the rest of the fixed vocabularies so a question cannot be tagged with a value nothing
# understands, and so a gap in coverage is a failing test rather than an oversight.


class SourceType(StrEnum):
    """Where the evidence for an answer has to come from."""

    POLICY = "policy"      # the policy documents alone
    HR = "hr"              # the employee's own record alone
    MIXED = "mixed"        # both, read against each other


class ReasoningType(StrEnum):
    """What the assistant has to do with the evidence once it has it."""

    DIRECT = "direct"              # the answer is stated in one clause or one field
    TEMPORAL = "temporal"          # depends on dates, effective periods, or versions
    SPANNING = "spanning"          # evidence combined across sections or documents
    COMPARATIVE = "comparative"    # two rules, leave types, or people compared
    NUMERICAL = "numerical"        # arithmetic, or a numeric rule interpreted
    RELATIONSHIP = "relationship"  # entities or conditions connected to each other
    HOLISTIC = "holistic"          # the whole of a policy summarised, not one fact


class ConversationType(StrEnum):
    """What the shape of the exchange demands, beyond the question itself."""

    FOLLOW_UP = "follow_up"        # only meaningful against an earlier turn
    MULTI_QUESTION = "multi_question"  # two or more distinct questions in one message
    AMBIGUOUS = "ambiguous"        # cannot be resolved confidently as asked
    CLARIFICATION = "clarification"  # something must be asked back before answering


class Modality(StrEnum):
    """The language the question is asked in, and the form the evidence takes."""

    ENGLISH = "english"
    ARABIC = "arabic"
    CODE_SWITCH = "code_switch"    # Arabic and English mixed in one question
    TABLE = "table"                # the answer lives in a row and column of a table
