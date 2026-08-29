"""
The shorthand employees use, and what it stands for.

Expanding these before searching matters: the policy documents spell everything out, so a
question asking about "AL" matches very little until it says "Annual Leave".
"""

import re

HR_ACRONYM_EXPANSIONS: dict[str, str] = {
    r"\bAL\b": "Annual Leave",
    r"\bSL\b": "Sick Leave",
    r"\bWFH\b": "Work From Home (Remote Work)",
    r"\bWFA\b": "Work From Anywhere",
    r"\bPIP\b": "Performance Improvement Plan (Probation Review)",
    r"\bEOSB\b": "End of Service Benefits (Gratuity)",
    r"\bEOB\b": "End of Service Benefits",
    r"\bGRT\b": "Gratuity Entitlement",
    r"\bHRBP\b": "HR Business Partner",
    r"\bDHA\b": "Dubai Health Authority",
    r"\bDOH\b": "Department of Health Abu Dhabi",
    r"\bMOH\b": "Ministry of Health",
    r"\bLM\b": "Line Manager",
    r"\bTL\b": "Team Lead",
    r"\bLTI\b": "Long Term Illness (Sick Leave)",
    r"\bPTO\b": "Paid Time Off (Annual Leave)",
    r"\bFWA\b": "Flexible Working Arrangement",
}


def expand_hr_acronyms(text: str) -> tuple[str, list[str]]:
    """The text with its shorthand spelled out, and which expansions were applied."""
    expanded_text = text
    applied_expansions: list[str] = []

    for pattern, expansion in HR_ACRONYM_EXPANSIONS.items():
        if re.search(pattern, expanded_text, re.IGNORECASE):
            expanded_text = re.sub(pattern, expansion, expanded_text, flags=re.IGNORECASE)
            applied_expansions.append(expansion)

    return expanded_text, applied_expansions
