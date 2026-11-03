"""Score the copilot's routing on a question set.

For each question we know which policy should answer it, or that it should be escalated.
Outcomes:
  correct          the right policy, or a correct escalation
  safe escalation  it should have answered but handed off to a person (no harm, lost time)
  wrong answer     it answered from the wrong policy (the dangerous case)

    python3 run_eval.py              # build set (questions used while building)
    python3 run_eval.py --unseen     # questions never used while building
"""
import csv
import sys
from pathlib import Path

from copilot.agent import route

EVALS = Path(__file__).resolve().parent / "evals"


def load(name):
    with open(EVALS / name, newline="") as f:
        return list(csv.DictReader(f))


def outcome(expected, got):
    if got == expected:
        return "correct"
    return "safe escalation" if got == "escalate" else "wrong answer"


def evaluate(rows):
    results = []
    for row in rows:
        decision = route(row["question"])
        got = "escalate" if decision["action"] == "escalate" else decision["passages"][0]["policy"]
        results.append({**row, "got": got, "score": decision["passages"][0]["score"], "outcome": outcome(row["expected"], got)})
    return results


def report(results, title):
    print(f"\n{title}")
    print("-" * len(title))
    for r in results:
        mark = {"correct": "OK  ", "safe escalation": "SAFE", "wrong answer": "WRONG"}[r["outcome"]]
        print(f"{mark:5} {r['score']:5.2f}  expected={r['expected']:<10} got={r['got']:<10} {r['question']}")
    counts = {o: sum(r["outcome"] == o for r in results) for o in ("correct", "safe escalation", "wrong answer")}
    print(f"\nCorrect: {counts['correct']}/{len(results)}  |  safe escalations: {counts['safe escalation']}  |  wrong answers: {counts['wrong answer']}")
    return counts


if __name__ == "__main__":
    if "--unseen" in sys.argv:
        report(evaluate(load("unseen_set.csv")), "Unseen set (never used while building)")
    else:
        report(evaluate(load("build_set.csv")), "Build set")
