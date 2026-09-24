"""Make the buildathon's 1,000 genuine Nansen API calls.

Only touches the cheap smart-money netflow endpoint (5 credits/call),
sweeping across chains, smart-money label cohorts, and sort orders.
Every call is a real, distinct query and is logged to .call_log.jsonl
with credits used/remaining.

    export NANSEN_API_KEY=<key>
    python backfill.py            # stops at 1,000 successful calls
    python backfill.py 1500       # custom target

Cost: 1,000 calls x 5 credits = 5,000 credits. During the buildathon
window (Sep 14-27) credit purchases are doubled, so a single $10 pack
(10,000 -> 20,000 credits) covers this several times over.
"""
import itertools
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ship_or_exit.nansen import NansenClient, NansenError

CHAINS = ["ethereum", "solana", "base", "arbitrum", "optimism", "bnb", "polygon"]
LABEL_SETS = [["Fund"], ["Smart Trader"], ["30D Smart Trader"], None]
SORTS = [("net_flow_7d_usd", "DESC"), ("net_flow_7d_usd", "ASC"),
         ("net_flow_30d_usd", "DESC")]


def main() -> int:
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    try:
        client = NansenClient()
    except NansenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    made = client.call_count()
    print(f"starting at {made} logged calls, target {target}")
    combos = itertools.cycle(itertools.product(CHAINS, LABEL_SETS, SORTS))
    for chain, labels, (field, direction) in combos:
        if made >= target:
            break
        try:
            client.netflow([chain], labels=labels, per_page=100,
                           order_field=field, direction=direction)
        except NansenError as exc:
            print(f"\nstopping early: {exc}", file=sys.stderr)
            break
        made = client.call_count()
        print(f"\r{made}/{target} calls | {client.credits_spent()} credits spent",
              end="", flush=True)
    print(f"\ndone: {made} successful calls logged to {client.log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
