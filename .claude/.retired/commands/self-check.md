---
description: "Run the configuration's own self-checks, read what they say, and act. Use when a session starts on a stale surface, before a deployment, or when `staleness.py` has flagged something. Not a report — the point is the decision at the end."
rex: []
---

Run this configuration's self-checks and **act on what they return**. Reading them
is the cheap half; the loop only closes if something changes or is explicitly
declared not-worth-changing.

## Why this is a command and not a hook

A hook on this binary (2.1.220) can run a command and emit a directive — it can
**not** spawn a subagent or launch a workflow (fact F3, verified on the binary,
not read in a book). So the continuous-engineering loop cannot fire itself.

A slash command can do what a hook cannot, because *you* are in the loop when it
runs: it can spawn agents, judge, and write. The binary exposes slash commands to
the model (`disable-model-invocation` is the opt-out, not the opt-in), so a
numbered rule in `CLAUDE.md` may name this command exactly as it names an agent.

The honest bound: this is **automatic conditional on a session existing**.
Nothing here fires while nobody is working. `staleness.py --quiet` runs at
`SessionStart` and says when a check has gone stale — that is the trigger, and
it is the closest thing to automatic that F3 permits.

## What to do

1. **Ask what is stale.**

   ```bash
   python3 tools/dev/staleness.py
   ```

   It reports the age of four checks against a declared threshold. It relaunches
   nothing: the bench costs a quota window, and that is not a hook's call.

2. **Run what it names, and only that.** Each stale entry prints its own command.
   Do not run the bench because the fleet check is stale — they answer different
   questions, and the bench is the expensive one.

3. **Read the output, not the exit code.** `verify_loop_wiring.py` prints `KO`
   per chain while still exiting 0 on the non-blocking ones. A green exit is not
   a green fleet.

4. **For every red, decide — and record the decision.**
   - Fixable now → fix it, then re-run the same check. A check you have not seen
     go green again has not been fixed, it has been edited.
   - Not fixable now → add it to `NEXT.md` §5 with what it costs and what it
     risks. An unrecorded red comes back as a surprise.
   - Not worth fixing → say so in `NEXT.md`, with the reason. A defect closed by
     silence reopens on the next reader.

5. **If a check found nothing but you expected it to**, suspect the check before
   the code. This repo has paid nine times for a guard that could not fail: a
   test never seen red is a presence test in disguise (REX R3).

## What this command deliberately does not do

- **It does not run the bench.** Two hours and a quota window are a human
  decision. When the bench is what is stale, it prints the command and stops.
- **It does not fix things silently.** Every change it makes is one you can see
  in the diff, and every change it declines is written down.
- **It does not report green on missing data.** A check with no recorded run is
  reported *unknown*, never *ok* — a dashboard that shows green on absent data is
  the failure REX R4 describes.
