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
question ──> guardrail ──> word mapping ──> Claude rewrite (V3) ──> search 18 policy passages ──> best score ≥ 2.5 ? ──> Claude answers from the top 3 passages, citing [S1]
                │                                  │                                                   │
                └── tries to change the rules      └── OFFTOPIC                                 no ──> escalate to a person
                         ──> escalate                    ──> escalate
```

1. **Guardrail:** requests like "ignore your instructions" are escalated before anything else.
2. **Word mapping:** customer words are mapped to policy words (couch → sofa, money back → refund).
3. **Query rewriting (V3):** Claude turns the customer's message into policy wording
   ("Delivery guys scratched my table" becomes "item arrived damaged"), or flags it as off-topic.
   This replaces the growing hand-written synonym list with a general fix.
4. **Search (retrieval):** the 8 policies are split into 18 short passages, each scored with BM25,
   a keyword search formula where rare words count more than common ones. The best 3 are kept.
5. **Escalation threshold:** if the best passage scores below 2.5, no policy really answers, so a person takes over.
6. **Answer (generation):** Claude writes the answer from those 3 passages only, cites each claim,
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
python3 run_eval.py --test50 --compare                      # V1 vs V2 vs V3 on 50 synthetic messages
python3 run_eval.py --test50 --answers                      # + Claude writes V3 answers, a second call checks them
```

V3 and `--answers` need Claude Code. V3 rewrites are saved in `results/rewrites.json`, so `--compare` re-runs without new calls.

## Results

Each question has a known right policy, or should be escalated. Outcomes are split by risk:
a **safe escalation** costs time, a **wrong answer** misinforms a customer.

| Version | Question set | Correct | Safe escalations | Wrong answers |
|---|---|---|---|---|
| V1, keywords only | Build set (20) | 15/20 | 5 | 0 |
| V2, + word mapping, threshold 2.5 | Build set (20) | 20/20 | 0 | 0 |
| V2 | **Unseen set (10)** | **7/10** | 1 | 2 |

The 20/20 is not proof: V2 was tuned on those questions. **The unseen score is the honest number.**

### V3 on 50 synthetic customer messages

The 50 messages were written **before** V3 was built and never used to tune it. They mix personas,
typos, long messages, edge cases and off-topic or adversarial requests. All are synthetic.

| Version | Correct | Safe escalations | Wrong answers | Off-topic and traps caught |
|---|---|---|---|---|
| V1, keywords only | 35/50 | 11 | 4 | 7/7 |
| V2, + word mapping | 38/50 | 6 | 6 | 7/7 |
| **V3, + Claude rewrite** | **47/50** | 0 | 3 | 7/7 |

V3 also scores 10/10 on the earlier unseen set (V2: 7/10).

**Answer quality (V3).** Claude wrote an answer for every message V3 routed to a policy. A second Claude call then
checked each claim against the sources. Of 37 written answers, **5 (14%) added a detail
that is not in the sources**, and 6 times Claude itself chose to escalate because the passages did not settle the question.
About **74% of policy questions** ended with a correct, fully grounded answer.
Full details: `results/results_test_set_50.json`.

### What the V2 misses taught (fixed by V3)

- "Lamp shade came cracked in the **box**" matched the P.O. **box** shipping rule. Keyword search reads words, not meaning.
- "Can I send a **gift** to my sister in London?" matched the **gift** card policy instead of international shipping.
- "Can I **send it back**?" was not mapped to "return", so it escalated. A safe miss.

### What V3 still teaches

- **Ungrounded answers are mostly "helpful extras":** "contact Client Care to start the replacement", "check the Orders page",
  or assuming the customer chose white glove. Each sounds reasonable but is not in the policy. Next step: tighten the answer
  prompt to forbid next steps that are not written in the sources, then re-test on a new set.
- **The remaining routing misses come from the policies themselves:** "Is shipping free?" lands on *Shipping regions*,
  while the answer sits in *Delivery*. Merging or renaming overlapping policies fixes this better than smarter search.
- **The judge is a model too:** a sample of its verdicts should be checked by a person before trusting the rate.

### Recommendation

Not ready for customers. Ready for an **agent-facing pilot**: agents are trained on when to trust an answer and when to escalate, and they review every answer before sending it.
V3 fixes most wording problems, at the cost of one extra Claude call per question (more latency and run cost).
The remaining misses come from how the policies are written, so the knowledge base needs fixing as much as the search.
Go-live for customers only at 90%+ on real, unseen tickets with no wrong answers.

## Project structure

```
policies/          8 Halden policies, the single source of truth
copilot/
  retrieval.py     split policies into passages, keyword scoring (BM25)
  agent.py         guardrail, word mapping, V3 rewrite, threshold, answer or escalate
  llm.py           prompts and calls to Claude (rewrite, answer, judge)
ask.py             command-line copilot
run_eval.py        scoring on the test sets
evals/             build_set.csv, unseen_set.csv, test_set_50.csv
results/           saved V3 rewrites and evaluation results (JSON)
CLAUDE.md          project rules given to Claude Code
```

## How I built it

I built this with Claude Code in the terminal. I framed the problem, wrote the rules in `CLAUDE.md`
(standard library only, never answer without a retrieved passage, test every change), and defined the test sets.
Claude Code wrote and revised the code; I checked every version against the evaluation before moving on.
The commit history shows the steps: V1, evaluation, V2, the unseen test, the 50-message test set, then V3.

Paul Morgantini · New York · paul.morgantini.nyc@gmail.com
