# ADR-008 — Work that waits on an input we do not have

- **Status:** Accepted
- **Date:** 2026-08-21
- **Deciders:** @1x7xxxxxxx

## Context

Six roadmap items had sat open with the same shape: the engineering
is understood, and the input it operates on does not exist yet. They are not
deferred by preference, and they are not blocked by a decision anyone can take.
They are waiting on the world.

Measured on production, 2026-08-21:

| Item | The missing input | Measured |
|---|---|---|
| R4 — more training data + per-tenant evaluation | tenants and labels | 1 live tenant with data; the model was trained on a single anonymised set (N=508 / 102 test) |
| R5 — champion/challenger retraining DAG | forward outcome pairs | `SELECT count(*) FROM ml_prediction_outcomes` → **0** |
| R6 — RR volume regressor (R²=0.23) | training volume | same single set; the roadmap already records "blocker = volume, not features" |
| R7 — resurrection tuning | a real saves time-series | `detect_saves_resurrection`'s thresholds (min_age 180 d, 2× baseline, min_spark 50) are heuristic and have never been calibrated against one |
| R14/C1 — Meta multi-account | a tenant with two ad accounts | 2 tenants, **1 ad account each**; `meta_campaigns` has no `account_id` column at all, so the schema is single-account by construction |
| R2 — landing + pixel + CAPI | four inputs, none present | no positioning/copy decision (the product's own voice, not an engineer's to invent), no Meta Pixel ID, no working Meta token (R13 is red), and no campaign to attribute |

ADR-007 removed four items that were measured as *unnecessary*. These are the
opposite case: they are necessary, and they cannot start. Keeping them in the
open list has the same cost — a read at every `/resume` — and one worse effect:
it makes the open list look like a backlog someone is failing to burn down, when
in fact every item on it is waiting correctly.

R5 deserves a note of its own. "Build the retraining DAG now, it will have data
later" is tempting and wrong: a champion/challenger comparison written against
zero pairs cannot be tested, so what would ship is an untested pipeline that
looks finished. The `ml_outcome_labeling` DAG that *produces* the pairs is
already built and running (migration 060); the pairs will accrue on their own.

## Decision

These six leave the open roadmap and become **conditions on an input**, each
with a query or observation that answers "has it arrived yet?".

| Item | Reopens when |
|---|---|
| R5 — retraining DAG | `SELECT count(*) FROM ml_prediction_outcomes WHERE y_dw IS NOT NULL` returns enough pairs to hold out a test set — order of a few hundred, not a handful |
| R4 — more data + per-tenant eval | a second tenant accumulates its own labelled history; per-tenant evaluation is meaningless with one |
| R6 — RR volume regressor | the same volume that unblocks R4; it was suppressed on an honest R²=0.23, not on a feature gap |
| R7 — resurrection tuning | a saves time-series exists — i.e. `s4a_song_saves_daily` carries enough dated rows to see a real resurrection |
| R14/C1 — Meta multi-account | any tenant declares a second ad account. Today the credentials form accepts one `account_id` and `meta_campaigns` cannot even record which account a row came from, so the trigger is a product request, not a silent condition |
| R2 — landing + pixel + CAPI | the first campaign is actually planned. Attribution is the one part with a deadline — `_fbp`/`_fbc`/UTM cannot be recovered retroactively — so the capture work starts **with** the campaign decision, not before it |

## Consequences

### Positive
- The open roadmap becomes what `/resume` needs it to be: work that could start
  today. After ADR-007 and this one, everything left is either actionable or
  waiting on a person, and the difference is visible at a glance.
- The measurements are preserved. "0 outcome pairs" and "no `account_id` column"
  are the expensive part; re-deriving them in three months is pure waste.
- R5's trap is written down, so nobody builds an untestable pipeline to feel
  productive.

### Negative / Trade-offs
- A condition nobody checks is a decision nobody revisits. Three of the five
  conditions are satisfied by the same event — a second active tenant — which is
  also the event most likely to be noticed. R14/C1's is a product request, which
  arrives loudly by definition. R7's is the quietest and could genuinely sit
  unnoticed.
- Someone reading only the active roadmap will no longer see that ML work is
  planned. The archive entries and this ADR are the record.

### Neutral / Operational
- `.claude/dev-docs/roadmap/archive.md` carries the per-item detail; this ADR
  carries the reasoning that is common to all six.
- Nothing here touches the ML work already delivered: the scoring DAG, the
  dashboard views, and the outcome-labelling loop keep running and keep
  accumulating exactly the input these items need.

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Build R5's retraining DAG now against zero pairs | It could not be tested, so what ships is an untested pipeline that looks finished — worse than nothing, because it stops anyone else from noticing the gap. |
| Build the CAPI endpoint now, without a pixel ID | The same trap as R5, one domain over: no pixel ID, no working Meta token, no campaign — so no event can be verified to arrive. What ships is a conversions integration that has never converted anything, and it looks finished. |
| Ship the landing with placeholder copy | The landing sits at the apex of the user's own domain and speaks in their product's voice. Inventing positioning for someone else's business and publishing it is not a default an engineer gets to take. |
| Build Meta multi-account speculatively | It is a brick: `meta_campaigns` needs an `account_id` column, the collector needs to iterate accounts, and every Meta view needs to decide whether to merge or split. Designing that against zero demand means guessing the product question, and the guess ships as schema. |
| Leave all five open with "BLOQUÉ" in the status column | That is what was done. The status never changed, and a status that never changes stops being read — including on the day it becomes false. |
