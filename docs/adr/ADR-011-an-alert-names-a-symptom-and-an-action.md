# ADR-011 — An alert names a symptom the artist can see, and an action someone can take

- **Status**: Accepted
- **Date**: 2026-08-23
- **Closes**: roadmap R43

## Context

On 2026-08-23 three nightly alerts were suppressed to "make the quiet nights quiet
again". The three suppressions were correct and each was measured — but they were decided
*ad hoc*, against the noise of that particular week. A rule that exists only as three past
decisions gets re-litigated the next time someone finds a signal they would like to send,
and the fleet drifts back toward an inbox nobody reads.

Two sources in the corpus state the rule this repo had been converging on by trial:

> "Alerting has shifted to a model in which fewer alerts are triggered, by focusing only
> on **symptoms that directly impact user experience**."
> — Majors, Fong-Jones et al., *Observability Engineering*, p.61

> "All paging alerts should also be **actionable**. Low-priority alerts that bother the
> on-call engineer every hour (or more frequently) disrupt productivity, and the fatigue
> such alerts induce […]"
> — Beyer, Jones, Petoff et al., *Site Reliability Engineering*, p.156

Majors et al. add the trap this repo has already stepped in (p.152): post-incident
reviews generate new alerts, each individually justified, and the accumulation is what
kills attention — not any single one of them.

## Decision

A nightly alert is sent only when **both** hold: it names a symptom an artist could
observe in the product, **and** it names an action a human can take tonight. Anything
that satisfies one but not the other is recorded — in `etl_run_log`, in the dashboard's
readiness matrix, in a log — and not mailed.

## Consequences

### Positive
- The three suppressions of 2026-08-23 stop being exceptions and become instances.
- A new detector must now answer two questions before it can mail: *what would the artist
  see?* and *what do I do about it at 23h?* Several existing detectors would not pass, and
  that is the point.
- It gives `data-quality-check-verdict.md` its principled reason to keep a task recorded
  rather than mailed (see ADR-012 and R42).

### Negative / Trade-offs
- A real degradation that is not yet artist-visible will be recorded and not mailed. That
  is deliberate: freshness and volume detectors already cover the paths that become
  artist-visible, and the alternative is the fatigue the sources describe.
- "Actionable tonight" is a judgement. It is written into each detector's docstring so the
  judgement is reviewable rather than implicit.

### Neutral / Operational
- Existing detectors are not rewritten by this ADR. It binds new ones and any detector
  whose noise is questioned.
- `check_row_dips` (R39) was written under this rule: a per-tenant collection dip is
  artist-visible (their numbers stop growing) and actionable (check that tenant's
  credentials and scope).

## Alternatives rejected

| Option | Why rejected |
|--------|--------------|
| Keep deciding case by case | Measured cost: three nights of alerts evaporating unnoticed, and a consolidated mail that had become skimmable. A rule that lives only in past decisions is re-litigated every time. |
| Severity levels (P1 mails, P2 logs) | Moves the argument to "what severity is this?" without answering it. The two questions above are answerable from the detector's own code; a severity label is not. |
| Alert on everything, filter in the mailbox | This is what fatigue *is*. Beyer p.156 and Majors p.152 both describe the outcome: attention degrades across ALL alerts, including the ones that mattered. |
