"""Ask Claude to write the answer, using only the passages we found.

The prototype calls Claude Code in print mode (`claude -p`), which runs on the
user's Claude subscription. In production this would call the Anthropic API instead.
If Claude Code is not installed, the copilot falls back to quoting the best passage.
"""
import shutil
import subprocess

PROMPT = """You are the Client Care Copilot for Halden & Co., a premium US home goods retailer (fictional, used in a case study).
Answer the customer's question using ONLY the numbered sources below.
Rules:
- Cite every claim inline with its source number, like [S1].
- If the sources do not contain the answer, reply exactly: "ESCALATE: " followed by a one-sentence reason.
- Never invent policies, prices, dates, discounts or codes.
- Under 80 words, warm, direct, plain text, no markdown.

SOURCES:
{sources}

CUSTOMER QUESTION: {question}"""


def build_prompt(question, passages):
    sources = "\n".join(f"[S{i}] ({p['title']}) {p['text']}" for i, p in enumerate(passages, 1))
    return PROMPT.format(sources=sources, question=question)


def claude_available():
    return shutil.which("claude") is not None


def ask_claude(prompt, timeout=120):
    result = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Claude Code returned an error")
    return result.stdout.strip()
