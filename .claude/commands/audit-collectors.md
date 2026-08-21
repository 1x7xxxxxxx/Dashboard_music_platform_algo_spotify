---
rex:
  - date: 2026-08-21
    issue: "Cross-cutting rule #6 mandates `/audit-collectors` after touching any collector, and this command audited another project's: acquisition.py (USB CDC STM32 frames), fanuc_reader.py (OPC UA CNC), background_ml.py. None exist here. It also pointed at `src/Application/`, an absent directory."
    fix: "Rewrote against the ten real modules in src/collectors/, around the one rule this repo actually enforces — a collector raises, it never returns None/[]/{} or breaks silently. The rule definitions and fix patterns now delegate to skills/audit-collectors/SKILL.md instead of being restated (and drifting) here."
    ref: "R36"
    severity: crit
---

# /audit-collectors

Audit every collector for the **silent success** anti-pattern: an API error is
swallowed, empty data is returned, zero rows are upserted, and the DAG task still
exits `SUCCESS`. Nothing alerts; the dashboard shows stale data.

A **collector** here is any module under `src/collectors/` that reads an external
API and persists to Postgres — Spotify, Spotify for Artists, YouTube, SoundCloud,
Instagram, Meta Ads, Apple Music.

This command enforces cross-cutting rule #6. The rule definitions and fix patterns
live in `.claude/skills/audit-collectors/SKILL.md` — **load it, do not restate it
here.** Two copies of a rule drift, and the copy the model reads is the one that
is wrong.

## What this command does

1. Load the `audit-collectors` skill.
2. For each module in `src/collectors/`, verify the mandatory rules:
   - **R1 — raise in `except`**: every `except Exception` on an ingest path must
     `raise`. Never `return None`, `return []`, `return {}`. A per-item skip is
     legitimate **only** when the caller filters it and the code says so in a
     comment (the `instagram_api_collector.py` insights case).
   - **R2 — no silent `break`**: a non-2xx status inside a pagination loop must
     raise, not `break` — a `break` truncates the page set and reports success.
   - **R3 — absent ≠ failed**: a read that fails raises (`CredentialLoadError`,
     `UnknownArtistError`); it never degrades into "nothing to read". A DB outage
     and "not connected yet" must not produce the same value.
   - **R4 — the write names its tenant**: every upsert payload on a tenant-scoped
     table carries `artist_id`, and `artist_id` is **not** in `update_columns` —
     an upsert never transfers ownership of a row.
3. Output the status table below.
4. For each FAIL: exact `file:line` + the corrective action.

## Audit status table format

```
| Collector                    | R1 raise | R2 break | R3 absent≠failed | R4 tenant |
|------------------------------|----------|----------|------------------|-----------|
| spotify_api.py               | ✅ PASS  | ✅ PASS  | ✅ PASS          | ✅ PASS   |
| youtube_collector.py         | ✅ PASS  | ✅ PASS  | ⚠️ WARN          | ✅ PASS   |
```

## Steps

1. `ls src/collectors/*.py` — audit every module, not a remembered list.
2. `grep -n "return None\|return \[\]\|return {}\|break" src/collectors/*.py` → R1, R2.
3. Read each `except Exception` block: does it distinguish absent from failed? → R3.
4. `python3 .claude/scripts/audit_tenant_writes.py` → R4, mechanically.
5. Output the table, then the detailed findings for every FAIL/WARN.

## Related

- Skill: `.claude/skills/audit-collectors/SKILL.md` (rule definitions, fix patterns,
  and the per-file status recorded at the last full audit).
- Cross-cutting rules #6 (collectors raise) and #8 (SQL identifier allowlists).
- `.claude/rules/python.md` — the tenant section, for R3 and R4.
