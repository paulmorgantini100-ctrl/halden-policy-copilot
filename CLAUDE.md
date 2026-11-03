# Halden Policy Copilot

Prototype for a consulting case study: a copilot that helps Client Care agents at Halden & Co.
(a fictional premium home goods retailer) answer policy questions from one source of truth.

## Goal
Answer returns, delivery, warranty, price match, loyalty, gift card and shipping questions
from the files in `policies/` only, cite the source, and escalate to a person when unsure.

## Rules for this project
- Python standard library only. Anyone must be able to clone and run it with `python3`.
- Keep the code short and readable: a consultant should understand it in 10 minutes.
- Never let the model answer without retrieved passages. No passage above the threshold means escalate.
- Every change to retrieval or thresholds must be checked with `python3 run_eval.py`.
- Report results on questions the copilot has never seen, not only on the ones used to tune it.

## Commands
- `python3 ask.py "question"` ask one question (uses `claude -p` if Claude Code is installed)
- `python3 ask.py --no-claude "question"` retrieval only
- `python3 run_eval.py` score the test sets
