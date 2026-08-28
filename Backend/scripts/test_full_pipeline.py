"""
scripts/test_full_pipeline.py — Test the complete LangGraph Pipeline (Router + RAG Agent)

Usage:
    cd Backend
    python scripts/test_full_pipeline.py

    # Interactive mode:
    python scripts/test_full_pipeline.py --interactive
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    """Run test cases through the full pipeline."""

    from app.orchestrator import process_query

    test_queries = [
        # Greetings (terminal — handled by Router)
        {"query": "Hi", "expected_intent": "greeting", "expect_sources": False},
        {"query": "Good Morning", "expected_intent": "greeting", "expect_sources": False},

        # Not in scope (terminal — handled by Router)
        {"query": "What's the capital of UAE?", "expected_intent": "not_in_scope", "expect_sources": False},

        # Ambiguous (terminal — awaiting clarification)
        {"query": "How many leaves can I take?", "expected_intent": "ambiguous", "expect_sources": False},

        # In scope (goes through RAG Agent)
        {"query": "Who is my manager?", "expected_intent": "in_scope", "expect_sources": True},
        {"query": "How many annual leave days do I have?", "expected_intent": "in_scope", "expect_sources": True},
        {"query": "What is the sick leave policy?", "expected_intent": "in_scope", "expect_sources": True},
    ]

    print("\n" + "=" * 70)
    print("FULL PIPELINE TEST (Router + RAG Agent)")
    print("=" * 70)

    passed = 0
    failed = 0

    for i, tc in enumerate(test_queries, 1):
        query = tc["query"]
        expected_intent = tc["expected_intent"]
        expect_sources = tc["expect_sources"]

        print(f"\n[{i}/{len(test_queries)}] Query: \"{query}\"")
        print("-" * 50)

        try:
            result = process_query(
                user_query=query,
                employee_id="EMP001",
                target_language="en",
            )

            intent = result.intent
            has_sources = len(result.sources) > 0

            intent_ok = intent == expected_intent
            sources_ok = has_sources == expect_sources

            print(f"  Intent: {intent} {'✅' if intent_ok else '❌ (expected: ' + expected_intent + ')'}")
            print(f"  Sources: {len(result.sources)} {'✅' if sources_ok else '❌'}")
            print(f"  Confidence: {result.confidence_score:.2f}")
            print(f"  Latency: {result.latency_ms}ms")
            print(f"  Tokens: {result.tokens_used}")

            if result.rewritten_query:
                print(f"  Rewritten: {result.rewritten_query[:60]}...")

            if result.is_awaiting_clarification:
                print(f"  Awaiting Clarification: True")

            # Preview answer
            answer_preview = result.answer[:120] + "..." if len(result.answer) > 120 else result.answer
            print(f"  Answer: {answer_preview}")

            if intent_ok and sources_ok:
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


def run_interactive():
    """Interactive mode — chat with the full pipeline."""

    from app.orchestrator import process_query

    print("\n" + "=" * 70)
    print("FULL PIPELINE — INTERACTIVE MODE")
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
            print(f"\n[Intent: {result.intent} | Confidence: {result.confidence_score:.2f} | {result.latency_ms}ms | {result.tokens_used} tokens]")

            # Print answer
            print(f"\n🤖 Assistant: {result.answer}")

            # Print sources if any
            if result.sources:
                print(f"\n📎 Sources ({len(result.sources)}):")
                for src in result.sources[:3]:
                    src_type = "📊 SQL" if src.source_type == "database" else "📄 Policy"
                    print(f"   {src_type} {src.title} ({src.section})")

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


def run_rag_agent_only():
    """Test the RAG Agent directly (bypass router)."""

    from app.agents.rag_agent import run_rag_agent

    test_queries = [
        "Who is my current line manager?",
        "How many annual leave days do I have remaining?",
        "What is the sick leave policy and medical certificate requirements?",
    ]

    print("\n" + "=" * 70)
    print("RAG AGENT DIRECT TEST (bypassing Router)")
    print("=" * 70)

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] Query: \"{query}\"")
        print("-" * 50)

        try:
            result = run_rag_agent(
                rewritten_query=query,
                employee_id="EMP001",
                target_language="en",
            )

            print(f"  Latency: {result['latency_ms']}ms")
            print(f"  Tokens: {result['tokens_used']}")
            print(f"  Sources: {len(result['sources'])}")

            # Source breakdown
            for src in result['sources'][:2]:
                src_type = "SQL" if src.get('source_type') == 'database' else "Policy"
                print(f"    - [{src_type}] {src.get('title', 'Unknown')}")

            # Answer preview
            answer = result['answer']
            answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
            print(f"  Answer: {answer_preview}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("RAG AGENT TEST COMPLETE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Test the Full LangGraph Pipeline")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--rag-only", "-r", action="store_true", help="Test RAG Agent only (bypass router)")
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.rag_only:
        run_rag_agent_only()
    else:
        run_test_cases()


if __name__ == "__main__":
    main()
