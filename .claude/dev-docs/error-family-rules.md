# The 18 rules — one per error family

Type: Doc (hand-written; the rules are judgement, the counts come from `make error-families`)
Uses: `.claude/dev-docs/error-class-families.md` (generated — membership and counts)
Persists in: this file

418 classes in eight weeks, 91 % never recur. Counts below are DECLARED memberships (`- family:` on every entry, R180, 2026-09-26) — the earlier regex guess had put 42 in `le-locataire` and 89 in `un-garde-qui-ne-garde-pas`; 213 classes matched two or more families and the first hit won in silence. The class is an INCIDENT; the family is the
unit a developer can hold in mind. Each family below carries **one rule** (what to do),
**one question** (what to ask in review), and **where it is caught**:

- **commit** — a pytest detector that reads the CODE (AST, never text) and blocks. It sees
  the shape of the code, never the running system.
- **nightly** — a periodic probe that reads the WORLD (production, CI, secrets, database,
  external APIs) and reports in the nightly recap. It sees what 5 000 green tests cannot:
  on 2026-09-26 the nightly mail had been silent for six months (R179) and Meta collection
  had been down since a secret rotation — both invisible to every commit guard, both found
  in minutes by running the real thing in production.

A family can need both. A rule without a detector is a wish; a detector without a rule is
a trap nobody understands.

| # | Family | Rule | Caught at |
|---|---|---|---|
| 1 | `le-locataire` (19) | Every read, write and join names its tenant — all of them, not the first. Tests run with **two** tenants. Tenant identity never falls back to the env (that is the admin's). | commit (AST: SQL names `artist_id`) + nightly (cross-tenant contamination scan) |
| 2 | `deux-surfaces-deux-nombres` (25) | A number has **one** definition (the gold layer); surfaces call it, never recompute it. | commit (metrics-layer ratchet) + nightly (gold invariants: surfaces agree) |
| 3 | `une-erreur-avalée-devient-une-absence` (23) | An `except` distinguishes « nothing to read » from « could not read », and the reader sees which. A failure never returns `{}`/`None`/`0` in silence. | commit (AST: `except` that returns empty) + nightly (**log scan**: errors logged by a task that ended SUCCESS — R179's exact shape) |
| 4 | `un-état-qui-déborde-de-sa-portée` (26) | State lives exactly as long as what created it: per run, per worker, per tenant — never shared by accident. | commit |
| 5 | `une-configuration-qui-diverge-de-la-prod` (43) | What the repo declares is what production runs — and a secret has **one** source: a stored copy never outranks the rotated original. | nightly (schema drift, env parity, secret fingerprints across env AND stored copies) |
| 6 | `un-nombre-affirmé-qui-n-a-pas-été-mesuré` (32) | A number shown or written was measured; an absence is shown as an absence, never as 0. Claims in docs carry the command that measured them. | commit |
| 7 | `le-message-parle-au-mauvais-lecteur` (20) | A message names a gesture ITS reader can perform, in its reader's words. | commit (catalogue of messages) |
| 8 | `un-cumul-pris-pour-un-quotidien` (12) | Every series declares its species — daily quantity or cumulative counter — in one registry; nothing guesses. | commit (registry completeness) |
| 9 | `le-temps-et-l-horloge` (19) | Timestamps are UTC-aware; every date says which clock produced it (event, collection, publisher). | commit (AST: naive `now()` bound to an aware column) |
| 10 | `un-travail-qui-n-arrive-nulle-part` (24) | Every computed result has a reader — wire it or delete it. | commit (reachability) + nightly (**the recap mail itself**: a check whose section never appears is dead) |
| 11 | `la-frontière-avec-le-dehors` (25) | What leaves the system — mail, request, payment, secret — is bounded, and tests cannot reach the outside. | commit (conftest boundaries) + nightly (public-surface secret sweep) |
| 12 | `un-seuil-écrit-d-instinct` (11) | A threshold comes from the real distribution, anchored to its population, with its measurement cited. | commit |
| 13 | `un-coût-payé-sans-contrepartie` (16) | Every cost (CI time, first screen, reader attention) has someone it pays for. | nightly (CI waste) |
| 14 | `un-contrôle-qui-ne-peut-jamais-passer` (13) | A check runs where its tools exist; « could not run » is reported, never counted as pass. | commit + nightly |
| 15 | `une-écriture-qui-écrase` (7) | A write never destroys what another just wrote — and it would be known. | commit |
| 16 | `l-instrument-ment-sur-ce-qu-il-mesure` (4) | An instrument is checked against a known truth before being trusted (RTK told four lies). | manual → probe when it recurs |
| — | **`un-garde-qui-ne-garde-pas` (64)** | **The meta-rule, applies to every row above**: a guard proves itself — it fabricates the defect and must see it (self-proving), reads STRUCTURE not text, and its scope is the PROPERTY, not a form. A guard never seen red guards nothing. | commit (`test_a_proof_calls_the_detector_it_proves`, structure-not-text ratchets) |
| — | **`un-document-qui-affirme-un-état-périmé` (35)** | **The meta-rule for prose**: what is written is generated or checked, never copied once. | commit (generated-document `--check` in pytest) |

## Three process rules that bind the table

1. **A red must be read.** A check that is red every day hides the next real hit (the
   `df-na-rep` heuristic was red for months; it hid a live `nan`). Either triage it to zero
   or delete it — never let it stay red.
2. **The world is probed, not only the code.** Anything that depends on production, CI, a
   secret or an external API gets a nightly probe, and its result reaches the nightly recap.
3. **A new class enters as an instance of a family** — `family:` declared, admission ticket
   (`recurrence`/`sites≥2`/`p1`) — or it is only a test. The family is the unit; the class
   is its history.
