"""Ask the policy copilot a question from the terminal.

    python3 ask.py "Can I return a sofa after 40 days?"
    python3 ask.py                  # interactive mode
    python3 ask.py --no-claude "..." # retrieval only, no model call
"""
import sys

from copilot.agent import respond


def show(question, use_claude):
    result = respond(question, use_claude=use_claude)
    print(f"\n[{result['mode']}] {result['answer']}\n")
    if result.get("mapped"):
        print("Words mapped: " + ", ".join(result["mapped"]))
    print("Sources considered:")
    for i, p in enumerate(result["passages"], 1):
        print(f"  S{i}  {p['score']:5.2f}  {p['title']}: {p['text'][:90]}...")
    print()


def main():
    args = sys.argv[1:]
    use_claude = "--no-claude" not in args
    args = [a for a in args if a != "--no-claude"]
    if args:
        show(" ".join(args), use_claude)
        return
    print("Halden Client Care Copilot. Type a customer question, or 'quit'.")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"quit", "exit", ""}:
            break
        show(question, use_claude)


if __name__ == "__main__":
    main()
