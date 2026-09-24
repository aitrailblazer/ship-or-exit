# Submission checklist

Deadline: **September 27, 2026, 23:59 UTC** (4:59 PM PDT). Submit early;
do not aim at the wire.

## Steps

1. [ ] Create a free Nansen API key at https://app.nansen.ai/api
2. [ ] `export NANSEN_API_KEY=<key>` then `python backfill.py`
        (1,000 genuine calls; verify with `.call_log.jsonl`)
3. [ ] `python run_live.py` for a real-data report (sanity check)
4. [ ] Screen-record `python demo.py` (terminal, under 90 seconds)
5. [ ] Post the demo on X: tag @nansen_ai, start the post with the
        triangle (draft below)
6. [ ] Push this repo to GitHub (public)
7. [ ] Submit via https://nansen-ai.typeform.com/meridian-submit
        (email + X post URL + GitHub repo URL)

## X post draft

```
🔺 I built Ship-or-Exit for the Nansen Meridian Buildathon.

Nansen shows where smart money flows. GitHub shows whether anyone is
still building. My agent fuses both and flags the divergence: heavy
inflows into a repo that went quiet.

Demo below. @nansen_ai
```

Attach the recording. Keep it under 90 seconds: problem, one
divergence example, what Nansen uniquely enables.

## Recording script (terminal)

1. `python demo.py` (full run, ~2 seconds)
2. Scroll to the `[!!] LDO EXIT_LIQUIDITY_RISK` block; read the thesis
   line aloud: "Smart money is accumulating but development has gone
   quiet."
3. Contrast with `[>>] UNI HIGH_CONVICTION`.
4. Close on: "Nansen drives the flow side; commits drive the reality
   check."
