# How Ship-or-Exit maps to the judging criteria

Each criterion is 25%. Here is exactly where each one is satisfied.

## 1. Nansen integration: data drives the logic

- The core signal (flow momentum: 7d vs 30d netflow rate, acceleration
  ratio, trader count) comes exclusively from Nansen Smart Money
  netflows (`POST /api/v1/smart-money/netflow`).
- Remove Nansen and the product has no flow side; the verdicts collapse.
  This is not decoration on a dashboard, it is the decision input.
- Credit discipline is engineered in: only 5-credit netflow calls are
  used; premium labels (100-500cr) and agent endpoints (200-750cr) are
  never touched. The per-call cost table is documented in README.

## 2. Originality: an agent, not a dashboard

- The crowded lanes in this buildathon are thesis/fact-check engines and
  prediction-market crossovers. Nobody is fusing onchain flows with
  protocol development activity.
- The product is a decision engine with six explainable verdicts,
  including EXIT_LIQUIDITY_RISK: the specific divergence where smart
  money accumulates into a repo that has gone quiet.
- GitHub commit data is filtered (merges, bots, dependency churn) and
  every repo is scored against its own baseline, not against others.

## 3. Functionality: deterministic demo path

- `python demo.py` runs the entire pipeline on synthetic fixtures with
  zero keys and zero network. This is the recording path; it cannot
  break on API flakiness because it touches no API.
- Live mode (`run_live.py`) isolates failures per token: one bad repo
  or one API error degrades to INSUFFICIENT_DATA/ERROR for that token,
  never kills the run.
- The demo fixtures cover all six verdicts, so the recording shows the
  full behavior in one take.

## 4. Documentation: runnable in under 10 minutes

- README quickstart is three commands: clone, pip install, python demo.py.
- One dependency (`requests`). Python 3.10+.
- `.env.example` documents the two optional keys. No key is needed to
  evaluate the product.
- SUBMIT.md holds the submission checklist so nothing is forgotten
  before the Sep 27, 23:59 UTC deadline.
