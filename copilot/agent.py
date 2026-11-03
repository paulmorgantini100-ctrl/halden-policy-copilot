"""The copilot's decision: answer from a policy, or hand off to a person."""
import re

from .llm import ask_claude, build_prompt, claude_available
from .retrieval import Retriever

# Below this score on the best passage, no policy really answers the question.
THRESHOLD = 3.0

# Requests that try to change the copilot's rules are escalated before any search.
INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\b.{0,40}\b(instruction|rule|prompt|polic)"
    r"|system prompt|jailbreak|act as|pretend (you|to)",
    re.IGNORECASE,
)

_retriever = None


def retriever():
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


def route(question):
    """Decide what to do. Returns a dict with action ("answer" or "escalate"), reason and passages."""
    passages = retriever().search(question)
    if INJECTION.search(question):
        return {"action": "escalate", "reason": "This request tries to change the copilot's rules", "passages": passages}
    if not passages or passages[0]["score"] < THRESHOLD:
        return {"action": "escalate", "reason": "No Halden policy answers this with confidence", "passages": passages}
    return {"action": "answer", "reason": "", "passages": passages}


def respond(question, use_claude=True):
    decision = route(question)
    if decision["action"] == "escalate":
        decision["answer"] = f"{decision['reason']}. Passing this to a Client Care specialist."
        decision["mode"] = "escalation"
        return decision
    if use_claude and claude_available():
        text = ask_claude(build_prompt(question, decision["passages"]))
        decision["answer"], decision["mode"] = text, "claude"
        if text.upper().startswith("ESCALATE"):
            decision["action"] = "escalate"
        return decision
    # Without a model, quote the passages from the best-matching policy.
    best = decision["passages"][0]
    quotes = [f"[S{i}] {p['text']}" for i, p in enumerate(decision["passages"], 1) if p["policy"] == best["policy"]]
    decision["answer"] = f"From our {best['title'].lower()}: " + " ".join(quotes)
    decision["mode"] = "retrieval only"
    return decision
