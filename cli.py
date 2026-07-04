"""Command-line interface for asking questions against the knowledge base.

Usage:
    python cli.py                 # interactive loop
    python cli.py "your question" # single question
"""
import sys

from src.rag import answer_question


def ask(question: str) -> None:
    result = answer_question(question)
    print("\nAnswer:\n" + result.text)
    if result.passages:
        print("\nSources:")
        for p in result.passages:
            print(f"  - {p.source} (similarity {p.score})")
    print()


def main() -> None:
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
        return

    print("RAG assistant — type a question (or 'exit' to quit).")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"exit", "quit", "q", ""}:
            break
        ask(question)


if __name__ == "__main__":
    main()
