"""The copilot's decision: answer from a policy, or hand off to a person.

Three versions are kept side by side so they can be compared on the same test sets:
  V1  keyword search only, escalation threshold 3.0
  V2  + a small customer-to-policy word map, threshold 2.5
  V3  + Claude rewrites the customer message into policy wording before the search,
      and flags off-topic messages (no hand-written synonyms needed for new cases)
"""
import re

from .llm import ask_claude, build_prompt, claude_available, rewrite_queries
from .retrieval import Retriever

# Below this score on the best passage, no policy really answers the question.
# V1 used 3.0. Lowered to 2.5 once customer wording is mapped to policy wording,
# after checking the scores of correct answers and off-topic questions in the build set.
THRESHOLDS = {1: 3.0, 2: 2.5, 3: 2.5}
THRESHOLD = THRESHOLDS[2]

# V2: customers and policies use different words. Add the policy word when a customer word appears.
SYNONYMS = {
    "couch": "sofa", "settee": "sofa",
    "refundable": "refund return", "refund": "refund return", "money back": "refund return",
    "scratched": "damaged", "scratch": "damaged", "dent": "damaged", "dented": "damaged",
    "broke": "broken damaged",
    "reward": "points loyalty", "rewards": "points loyalty",
    "po": "p.o. box", "website": "online",
    "ship": "ship delivery", "canada": "canada international",
}

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


def expand(question):
    """Return the question with policy words added, and the list of mappings used."""
    text, used = question.lower(), []
    for customer_word, policy_words in SYNONYMS.items():
        if re.search(rf"\b{re.escape(customer_word)}\b", text):
            text += " " + policy_words
            used.append(f"{customer_word} -> {policy_words}")
    return text, used


def route(question, version=2, rewrite=None):
    """Decide what to do. Returns a dict with action ("answer" or "escalate"), reason and passages.

    For V3, pass the Claude rewrite of the question (or let this function ask Claude for it).
    """
    if version == 1:
        query, mapped = question, []
    else:
        query, mapped = expand(question)
    if version == 3:
        if rewrite is None:
            rewrite = rewrite_queries([question])[0] if claude_available() else ""
        if rewrite and rewrite.upper() != "OFFTOPIC":
            query += " " + rewrite
    passages = retriever().search(query)
    base = {"passages": passages, "mapped": mapped, "rewrite": rewrite, "version": version}
    if INJECTION.search(question):
        return {**base, "action": "escalate", "reason": "This request tries to change the copilot's rules"}
    if version == 3 and rewrite and rewrite.upper() == "OFFTOPIC":
        return {**base, "action": "escalate", "reason": "This is not a question about Halden policies"}
    if not passages or passages[0]["score"] < THRESHOLDS[version]:
        return {**base, "action": "escalate", "reason": "No Halden policy answers this with confidence"}
    return {**base, "action": "answer", "reason": ""}


def respond(question, use_claude=True, version=None):
    if version is None:
        version = 3 if use_claude and claude_available() else 2
    decision = route(question, version=version)
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
