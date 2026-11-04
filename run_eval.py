"""Score the copilot on a question set, and compare versions.

Routing outcomes (does the copilot pick the right policy, or correctly hand off?):
  correct          the right policy, or a correct escalation
  safe escalation  it should have answered but handed off to a person (no harm, lost time)
  wrong answer     it answered from the wrong policy (the dangerous case)

Answer outcomes (--answers, needs Claude Code): Claude writes each answer from the
retrieved passages, then a second Claude call checks that every claim is in the sources.
  hallucination    an answer with at least one claim that is not in the sources

    python3 run_eval.py                       # build set, V2
    python3 run_eval.py --unseen              # 10 unseen questions, V2
    python3 run_eval.py --test50 --compare    # 50-message test set, V1 vs V2 vs V3
    python3 run_eval.py --test50 --answers    # + write and judge V3 answers
"""
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from copilot.agent import route
from copilot.llm import ask_claude, build_prompt, claude_available, format_sources, judge_answers, rewrite_queries

ROOT = Path(__file__).resolve().parent
EVALS, RESULTS = ROOT / "evals", ROOT / "results"
REWRITE_CACHE = RESULTS / "rewrites.json"


def load(name):
    with open(EVALS / name, newline="") as f:
        return list(csv.DictReader(f))


def outcome(expected, got):
    if got in expected.split("|"):
        return "correct"
    return "safe escalation" if got == "escalate" else "wrong answer"


def get_rewrites(questions):
    """V3 rewrites, cached so the comparison can be re-run without calling Claude again."""
    cache = json.loads(REWRITE_CACHE.read_text()) if REWRITE_CACHE.exists() else {}
    missing = [q for q in questions if q not in cache]
    if missing:
        if not claude_available():
            raise SystemExit("V3 needs Claude Code (claude -p) for questions not in results/rewrites.json")
        for q, r in zip(missing, rewrite_queries(missing)):
            cache[q] = r
        RESULTS.mkdir(exist_ok=True)
        REWRITE_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    return [cache[q] for q in questions]


def evaluate(rows, version):
    rewrites = get_rewrites([r["question"] for r in rows]) if version == 3 else [None] * len(rows)
    results = []
    for row, rw in zip(rows, rewrites):
        d = route(row["question"], version=version, rewrite=rw)
        got = "escalate" if d["action"] == "escalate" else d["passages"][0]["policy"]
        results.append({**row, "got": got, "score": round(d["passages"][0]["score"], 2), "rewrite": rw,
                        "outcome": outcome(row["expected"], got), "passages": d["passages"], "action": d["action"]})
    return results


def summarize(results):
    n = len(results)
    count = lambda o: sum(r["outcome"] == o for r in results)
    answerable = [r for r in results if r["expected"] != "escalate"]
    offtopic = [r for r in results if r["expected"] == "escalate"]
    return {
        "questions": n,
        "accuracy": round(count("correct") / n, 3),
        "correct": count("correct"),
        "safe_escalations": count("safe escalation"),
        "wrong_answers": count("wrong answer"),
        "retrieval_success": round(sum(r["outcome"] == "correct" for r in answerable) / len(answerable), 3) if answerable else None,
        "escalation_rate": round(sum(r["got"] == "escalate" for r in results) / n, 3),
        "offtopic_caught": round(sum(r["got"] == "escalate" for r in offtopic) / len(offtopic), 3) if offtopic else None,
    }


def report(results, title):
    print(f"\n{title}\n" + "-" * len(title))
    for r in results:
        mark = {"correct": "OK  ", "safe escalation": "SAFE", "wrong answer": "WRONG"}[r["outcome"]]
        print(f"{mark:5} {r['score']:5.2f}  expected={r['expected']:<16} got={r['got']:<10} {r['question'][:70]}")
    s = summarize(results)
    print(f"\nCorrect: {s['correct']}/{s['questions']}  |  safe escalations: {s['safe_escalations']}  |  wrong answers: {s['wrong_answers']}")
    return s


def judge(results):
    """Write V3 answers with Claude for every routed question, then have Claude check them against their sources."""
    routed = [r for r in results if r["action"] == "answer"]

    def write(r):
        answer = ask_claude(build_prompt(r["question"], r["passages"]))
        print(f"  answered: {r['question'][:60]}", flush=True)
        return {"question": r["question"], "expected": r["expected"], "got": r["got"],
                "sources": format_sources(r["passages"]), "answer": answer}

    with ThreadPoolExecutor(max_workers=6) as pool:  # a few calls at once to keep the run short
        items = list(pool.map(write, routed))
    verdicts = []
    for start in range(0, len(items), 10):
        verdicts += judge_answers(items[start:start + 10])
    for item, v in zip(items, verdicts):
        item["faithful"], item["unsupported"] = bool(v.get("faithful")), v.get("unsupported", "")
    written = [i for i in items if not i["answer"].upper().startswith("ESCALATE")]
    return items, {
        "answers_written": len(written),
        "model_escalations": len(items) - len(written),
        "hallucinations": sum(not i["faithful"] for i in written),
        "hallucination_rate": round(sum(not i["faithful"] for i in written) / len(written), 3) if written else None,
    }


def strip(results):
    return [{k: v for k, v in r.items() if k not in ("passages", "action")} for r in results]


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--test50" in args:
        name, label = "test_set_50.csv", "50-message test set"
    elif "--unseen" in args:
        name, label = "unseen_set.csv", "Unseen set (never used while building)"
    else:
        name, label = "build_set.csv", "Build set"
    rows = load(name)

    if "--compare" not in args and "--answers" not in args:
        report(evaluate(rows, 2), f"{label}, V2")
        raise SystemExit

    out = {"set": name, "versions": {}}
    per_version = {}
    for v in (1, 2, 3):
        per_version[v] = evaluate(rows, v)
        out["versions"][f"V{v}"] = report(per_version[v], f"{label}, V{v}")
    out["details"] = {f"V{v}": strip(r) for v, r in per_version.items()}

    if "--answers" in args:
        print("\nWriting and judging V3 answers with Claude...")
        items, answer_stats = judge(per_version[3])
        out["answers_V3"] = answer_stats
        out["answer_details"] = items
        print(f"\nV3 answers: {answer_stats}")

    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"results_{Path(name).stem}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nSaved {path.relative_to(ROOT)}")
