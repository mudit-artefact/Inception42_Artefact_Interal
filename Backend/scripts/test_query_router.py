"""
scripts/test_query_router.py — Standalone test script for Query Router

Usage:
    cd Backend
    python scripts/test_query_router.py

    # Interactive mode:
    python scripts/test_query_router.py --interactive
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv()

from app.agents.query_router import route_query, QueryRouterState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# TEST CASES
# ══════════════════════════════════════════════════════════════════════════════

TEST_CASES = [
    # Greetings
    {"query": "Hi", "expected_intent": "greeting"},
    {"query": "Good Morning", "expected_intent": "greeting"},
    {"query": "Hello", "expected_intent": "greeting"},
    {"query": "مرحبا", "expected_intent": "greeting", "lang": "ar"},
    {"query": "السلام عليكم", "expected_intent": "greeting", "lang": "ar"},

    # Not in scope
    {"query": "What's the capital of UAE?", "expected_intent": "not_in_scope"},
    {"query": "How to cook biryani?", "expected_intent": "not_in_scope"},
    {"query": "Tell me a joke", "expected_intent": "not_in_scope"},
    {"query": "What's the weather today?", "expected_intent": "not_in_scope"},

    # Ambiguous
    {"query": "How many leaves can I take?", "expected_intent": "ambiguous"},
    {"query": "What's the approval process?", "expected_intent": "ambiguous"},
    {"query": "Can I work remotely?", "expected_intent": "ambiguous"},
    {"query": "What's my balance?", "expected_intent": "ambiguous"},

    # In scope
    {"query": "Who is my manager?", "expected_intent": "in_scope"},
    {"query": "How many annual leave days do I have?", "expected_intent": "in_scope"},
    {"query": "What is the sick leave policy?", "expected_intent": "in_scope"},
    {"query": "How do I submit an expense claim?", "expected_intent": "in_scope"},
    {"query": "What's my AL balance?", "expected_intent": "in_scope"},
    {"query": "كم يوم إجازة سنوية متبقي لي؟", "expected_intent": "in_scope", "lang": "ar"},
]


def print_result(result: QueryRouterState, expected_intent: str | None = None):
    """Pretty print the router result."""

    intent = result.get("intent", "unknown")
    confidence = result.get("confidence", 0.0)
    is_terminal = result.get("is_terminal", False)
    is_awaiting = result.get("is_awaiting_clarification", False)

    # Check if intent matches expected
    match_icon = ""
    if expected_intent:
        if intent == expected_intent:
            match_icon = "✅"
        else:
            match_icon = f"❌ (expected: {expected_intent})"

    print(f"  Intent: {intent} ({confidence:.2f}) {match_icon}")
    print(f"  Terminal: {is_terminal} | Awaiting Clarification: {is_awaiting}")

    if result.get("response"):
        response = result["response"]
        if len(response) > 150:
            response = response[:150] + "..."
        print(f"  Response: {response}")

    if result.get("rewritten_query"):
        print(f"  Rewritten: {result['rewritten_query']}")

    if result.get("clarifying_question"):
        print(f"  Clarifying Q: {result['clarifying_question']}")


def run_test_cases():
    """Run all predefined test cases."""

    print("\n" + "=" * 70)
    print("QUERY ROUTER — AUTOMATED TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    import time
    for i, tc in enumerate(TEST_CASES, 1):
        query = tc["query"]
        expected = tc["expected_intent"]
        lang = tc.get("lang", "en")

        print(f"\n[{i}/{len(TEST_CASES)}] Query: \"{query}\"")
        print("-" * 50)

        try:
            result = route_query(
                user_query=query,
                employee_id="EMP001",
                employee_name="Ahmed Al Mansoori",
                employee_name_ar="أحمد المنصوري",
                target_language=lang,
            )

            print_result(result, expected)

            if result.get("intent") == expected:
                passed += 1
            else:
                failed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

        time.sleep(1.5)

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(TEST_CASES)}")
    print("=" * 70)

    return failed == 0


def run_clarification_test():
    """Test the ambiguous → clarification → in_scope flow."""

    print("\n" + "=" * 70)
    print("QUERY ROUTER — CLARIFICATION FLOW TEST")
    print("=" * 70)

    # Step 1: Ambiguous query
    print("\n[Step 1] Initial ambiguous query")
    print("-" * 50)

    result1 = route_query(
        user_query="How many leaves can I take?",
        employee_id="EMP001",
        employee_name="Ahmed Al Mansoori",
        employee_name_ar="أحمد المنصوري",
        target_language="en",
    )
    print_result(result1, "ambiguous")

    if not result1.get("is_awaiting_clarification"):
        print("  ⚠️ Expected is_awaiting_clarification=True")
        return False

    # Step 2: User provides clarification
    print("\n[Step 2] User clarifies: 'Annual leave'")
    print("-" * 50)

    result2 = route_query(
        user_query="Annual leave",  # User's clarification
        employee_id="EMP001",
        employee_name="Ahmed Al Mansoori",
        employee_name_ar="أحمد المنصوري",
        target_language="en",
        original_question=result1.get("original_question"),
        user_clarification="Annual leave",
    )
    print_result(result2)

    if result2.get("is_terminal"):
        print("  ⚠️ Expected is_terminal=False (should continue to RAG)")
        return False

    if not result2.get("rewritten_query"):
        print("  ⚠️ Expected rewritten_query to be set")
        return False

    print("\n✅ Clarification flow works correctly!")
    return True


def run_interactive():
    """Interactive mode — chat with the router."""

    print("\n" + "=" * 70)
    print("QUERY ROUTER — INTERACTIVE MODE")
    print("Type 'quit' or 'exit' to stop")
    print("=" * 70)

    # State for clarification flow
    original_question = None
    awaiting_clarification = False

    while True:
        try:
            user_input = input("\n> You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            # Check if this is a clarification response
            if awaiting_clarification and original_question:
                result = route_query(
                    user_query=user_input,
                    employee_id="EMP001",
                    employee_name="Ahmed Al Mansoori",
                    employee_name_ar="أحمد المنصوري",
                    target_language="en",
                    original_question=original_question,
                    user_clarification=user_input,
                )
                # Reset clarification state
                original_question = None
                awaiting_clarification = False
            else:
                result = route_query(
                    user_query=user_input,
                    employee_id="EMP001",
                    employee_name="Ahmed Al Mansoori",
                    employee_name_ar="أحمد المنصوري",
                    target_language="en",
                )

            # Print response
            print(f"\n[Intent: {result.get('intent')} | Confidence: {result.get('confidence', 0):.2f}]")

            if result.get("response"):
                print(f"\n🤖 Assistant: {result['response']}")

            if result.get("rewritten_query"):
                print(f"\n📝 Rewritten for RAG: {result['rewritten_query']}")
                print("   → Ready to pass to RAG pipeline")

            # Check if awaiting clarification
            if result.get("is_awaiting_clarification"):
                original_question = result.get("original_question")
                awaiting_clarification = True
                print("\n   [Waiting for your clarification...]")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Test the Query Router")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--clarify", "-c", action="store_true", help="Test clarification flow")
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.clarify:
        run_clarification_test()
    else:
        # Run all tests + clarification test
        success = run_test_cases()
        run_clarification_test()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
