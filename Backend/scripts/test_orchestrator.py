"""
scripts/test_orchestrator.py — Test the integrated Orchestrator (Router + RAG)

Usage:
    cd Backend
    python scripts/test_orchestrator.py

    # Interactive mode:
    python scripts/test_orchestrator.py --interactive
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_test_cases():
    """Run test cases through the orchestrator."""

    from app.orchestrator import process_query

    test_queries = [
        # Greetings (terminal)
        {"query": "Hi", "expected_terminal": True, "expected_intent": "greeting"},
        {"query": "Good Morning", "expected_terminal": True, "expected_intent": "greeting"},

        # Not in scope (terminal)
        {"query": "What's the capital of UAE?", "expected_terminal": True, "expected_intent": "not_in_scope"},
        {"query": "Tell me a joke", "expected_terminal": True, "expected_intent": "not_in_scope"},

        # Ambiguous (terminal, awaiting clarification)
        {"query": "How many leaves can I take?", "expected_terminal": True, "expected_intent": "ambiguous"},

        # In scope (non-terminal, continues to RAG)
        {"query": "Who is my manager?", "expected_terminal": False, "expected_intent": "in_scope"},
        {"query": "How many annual leave days do I have?", "expected_terminal": False, "expected_intent": "in_scope"},
        {"query": "What is the sick leave policy?", "expected_terminal": False, "expected_intent": "in_scope"},
    ]

    print("\n" + "=" * 70)
    print("ORCHESTRATOR — INTEGRATION TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for i, tc in enumerate(test_queries, 1):
        query = tc["query"]
        expected_terminal = tc["expected_terminal"]
        expected_intent = tc["expected_intent"]

        print(f"\n[{i}/{len(test_queries)}] Query: \"{query}\"")
        print("-" * 50)

        try:
            result = process_query(
                user_query=query,
                employee_id="EMP001",
                target_language="en",
            )

            intent = result.intent
            is_terminal = result.is_awaiting_clarification or (intent in ["greeting", "not_in_scope", "ambiguous"])

            # For in_scope, check if we got sources from RAG
            if intent == "in_scope":
                is_terminal = False

            intent_match = intent == expected_intent
            terminal_match = is_terminal == expected_terminal

            status = "✅" if (intent_match and terminal_match) else "❌"

            print(f"  Intent: {intent} {'✅' if intent_match else '❌ (expected: ' + expected_intent + ')'}")
            print(f"  Terminal: {is_terminal} {'✅' if terminal_match else '❌ (expected: ' + str(expected_terminal) + ')'}")
            print(f"  Confidence: {result.confidence_score:.2f}")
            print(f"  Latency: {result.latency_ms}ms")

            if result.answer:
                answer_preview = result.answer[:100] + "..." if len(result.answer) > 100 else result.answer
                print(f"  Answer: {answer_preview}")

            if result.rewritten_query:
                print(f"  Rewritten: {result.rewritten_query}")

            if result.sources:
                print(f"  Sources: {len(result.sources)} citations")

            if result.is_awaiting_clarification:
                print(f"  Awaiting Clarification: True")
                print(f"  Original Q: {result.original_question}")

            if intent_match and terminal_match:
                passed += 1
            else:
                failed += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_queries)}")
    print("=" * 70)

    return failed == 0


def run_clarification_flow():
    """Test the complete ambiguous → clarification → RAG flow."""

    from app.orchestrator import process_query

    print("\n" + "=" * 70)
    print("ORCHESTRATOR — CLARIFICATION FLOW TEST")
    print("=" * 70)

    # Step 1: Ambiguous query
    print("\n[Step 1] Ambiguous query: 'How many leaves can I take?'")
    print("-" * 50)

    result1 = process_query(
        user_query="How many leaves can I take?",
        employee_id="EMP001",
        target_language="en",
    )

    print(f"  Intent: {result1.intent}")
    print(f"  Awaiting Clarification: {result1.is_awaiting_clarification}")
    print(f"  Response: {result1.answer[:100]}...")

    if not result1.is_awaiting_clarification:
        print("  ⚠️ Expected is_awaiting_clarification=True")
        return False

    # Step 2: User clarifies
    print("\n[Step 2] User clarifies: 'Annual leave'")
    print("-" * 50)

    result2 = process_query(
        user_query="Annual leave",
        employee_id="EMP001",
        target_language="en",
        original_question=result1.original_question,
        user_clarification="Annual leave",
    )

    print(f"  Intent: {result2.intent}")
    print(f"  Rewritten Query: {result2.rewritten_query}")
    print(f"  Sources: {len(result2.sources)}")
    print(f"  Answer: {result2.answer[:150]}...")

    if result2.is_awaiting_clarification:
        print("  ⚠️ Expected is_awaiting_clarification=False")
        return False

    if len(result2.sources) == 0:
        print("  ⚠️ Expected sources from RAG")
        return False

    print("\n✅ Clarification flow works correctly!")
    return True


def run_interactive():
    """Interactive mode — chat with the orchestrator."""

    from app.orchestrator import process_query

    print("\n" + "=" * 70)
    print("ORCHESTRATOR — INTERACTIVE MODE")
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
                result = process_query(
                    user_query=user_input,
                    employee_id="EMP001",
                    target_language="en",
                    original_question=original_question,
                    user_clarification=user_input,
                )
                original_question = None
                awaiting_clarification = False
            else:
                result = process_query(
                    user_query=user_input,
                    employee_id="EMP001",
                    target_language="en",
                )

            # Print metadata
            print(f"\n[Intent: {result.intent} | Confidence: {result.confidence_score:.2f} | {result.latency_ms}ms]")

            # Print answer
            print(f"\n🤖 Assistant: {result.answer}")

            # Print sources if any
            if result.sources:
                print(f"\n📎 Sources ({len(result.sources)}):")
                for src in result.sources[:3]:
                    print(f"   - {src.title} ({src.section})")

            # Check if awaiting clarification
            if result.is_awaiting_clarification:
                original_question = result.original_question
                awaiting_clarification = True
                print("\n   [Waiting for your clarification...]")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Test the Orchestrator")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--clarify", "-c", action="store_true", help="Test clarification flow")
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.clarify:
        run_clarification_flow()
    else:
        success = run_test_cases()
        run_clarification_flow()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
