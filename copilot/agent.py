"""The copilot's decision: answer from a policy, or hand off to a person."""
import re

from .llm import ask_claude, build_prompt, claude_available
from .retrieval import Retriever

# Below this score on the best passage, no policy really answers the question.
# V1 used 3.0. Lowered to 2.5 once customer wording is mapped to policy wording,
# after checking the scores of correct answers and off-topic questions in the build set.
THRESHOLD = 2.5

# Customers and policies use different words. Add the policy word when a customer word appears.
# Maintained by Client Care: each new miss in review becomes a new line here.
SYNONYMS = {
    "couch": "sofa", "settee": "sofa",
    "refundable": "refund return", "refund": "refund return", "money back": "refund return",
    "scratched": "damaged", "scratch": "damaged", "dent": "damaged", "dented": "damaged",
    "broke": "broken damaged",
    "reward": "points loyalty", "rewards": "points loyalty",
    "po": "p.o. box", "website": "online",
    "ship": "ship delivery", "canada": "canada international",
}


def expand(question):
    """Return the question with policy words added, and the list of mappings used."""
    text, used = question.lower(), []
    for customer_word, policy_words in SYNONYMS.items():
        if re.search(rf"\b{re.escape(customer_word)}\b", text):
            text += " " + policy_words
            used.append(f"{customer_word} -> {policy_words}")
    return text, used

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
    expanded, mapped = expand(question)
    passages = retriever().search(expanded)
    base = {"passages": passages, "mapped": mapped}
    if INJECTION.search(question):
        return {**base, "action": "escalate", "reason": "This request tries to change the copilot's rules"}
    if not passages or passages[0]["score"] < THRESHOLD:
        return {**base, "action": "escalate", "reason": "No Halden policy answers this with confidence"}
    return {**base, "action": "answer", "reason": ""}


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
