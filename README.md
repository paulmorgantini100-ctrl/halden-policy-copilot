# Halden Policy Copilot

A prototype AI copilot for Client Care agents, built for a consulting case study.
It answers customer policy questions (returns, delivery, warranty, price match, loyalty, gift cards, shipping)
from one source of truth, cites the policy it used, and hands off to a person when it is not sure.

**Case study (business context, use-case prioritization, business case, roadmap):**
https://claude.ai/artifact/FAJSaJ4zPDrBLiAmvEm6Yn

> Halden & Co. is a fictional premium US home goods retailer. Policies and test questions are synthetic.

## The problem it solves

Halden's 45 Client Care agents handle 210K tickets a year. 46% are policy questions whose answer is already
written somewhere, but in four places that disagree (help center, wiki, PDFs, Slack). Agents lose minutes per
ticket searching, and new hires take weeks to answer with confidence.

**Before:** a customer asks "Can I return my couch after 3 weeks?" and the agent searches four sources.
**After:** the agent types the question and gets, in seconds, "Yes, sofas have a 30-day window and a $149 pickup fee [S1]",
with the policy passage shown. The agent checks it and sends.

## How it works

```
question ──> guardrail ──> word mapping ──> search 18 policy passages ──> best score ≥ 2.5 ? ──> Claude answers from the top 3 passages, citing [S1]
                │                                                              │
                └── tries to change the rules ──> escalate              no ──> escalate to a person
```

1. **Guardrail:** requests like "ignore your instructions" are escalated before anything else.
2. **Word mapping:** customer words are mapped to policy words (couch → sofa, money back → refund).
3. **Search (retrieval):** the 8 policies are split into 18 short passages, each scored with BM25,
   a keyword search formula where rare words count more than common ones. The best 3 are kept.
4. **Escalation threshold:** if the best passage scores below 2.5, no policy really answers, so a person takes over.
5. **Answer (generation):** Claude writes the answer from those 3 passages only, cites each claim,
   and replies `ESCALATE` if the passages do not contain the answer. This is retrieval-augmented generation (RAG).

The prototype calls Claude through Claude Code (`claude -p`). In production it would call the Anthropic API.
Without Claude Code installed, it still works in retrieval-only mode and quotes the matching policy.

## Run it

Python 3 standard library only, nothing to install.

```bash
python3 ask.py "Can I return my couch? I've had it 3 weeks"   # one question
python3 ask.py                                              # interactive mode
python3 ask.py --no-claude "Do you price match Wayfair?"     # retrieval only
python3 run_eval.py                                         # build set
python3 run_eval.py --unseen                                # questions never used while building
```

## Results

Each question has a known right policy, or should be escalated. Outcomes are split by risk:
a **safe escalation** costs time, a **wrong answer** misinforms a customer.

| Version | Question set | Correct | Safe escalations | Wrong answers |
|---|---|---|---|---|
| V1, keywords only | Build set (20) | 15/20 | 5 | 0 |
| V2, + word mapping, threshold 2.5 | Build set (20) | 20/20 | 0 | 0 |
| V2 | **Unseen set (10)** | **7/10** | 1 | 2 |

The 20/20 is not proof: V2 was tuned on those questions. **The unseen score is the honest number.**

### What the misses teach

- "Lamp shade came cracked in the **box**" matched the P.O. **box** shipping rule. Keyword search reads words, not meaning.
- "Can I send a **gift** to my sister in London?" matched the **gift** card policy instead of international shipping.
- "Can I **send it back**?" was not mapped to "return", so it escalated. A safe miss.

### Recommendation

Not ready for customers. Ready for an **agent-facing pilot**: agents are trained on when to trust an answer and when to escalate, and they review every answer before sending it.
Next step: add meaning-based search (embeddings) alongside keywords, then re-test on a fresh unseen set.
Go-live for customers only at 90%+ on unseen questions with no wrong answers.

## Project structure

```
policies/          8 Halden policies, the single source of truth
copilot/
  retrieval.py     split policies into passages, keyword scoring (BM25)
  agent.py         guardrail, word mapping, threshold, answer or escalate
  llm.py           prompt and call to Claude
ask.py             command-line copilot
run_eval.py        scoring on the test sets
evals/             build_set.csv and unseen_set.csv
CLAUDE.md          project rules given to Claude Code
```

## How I built it

I built this with Claude Code in the terminal. I framed the problem, wrote the rules in `CLAUDE.md`
(standard library only, never answer without a retrieved passage, test every change), and defined the test sets.
Claude Code wrote and revised the code; I checked every version against the evaluation before moving on.
The commit history shows the steps: V1, evaluation, V2, then the unseen test.

Paul Morgantini · New York · paul.morgantini.nyc@gmail.com
