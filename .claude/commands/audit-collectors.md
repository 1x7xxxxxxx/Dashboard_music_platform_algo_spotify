---
rex: []
---

# /audit-collectors

Audit all data collector modules for the 4 mandatory safety rules.

A **collector** in MSDR is any module that reads from an external source and persists data:
- `acquisition.py` — USB CDC serial reader (STM32 accelerometer frames)
- `fanuc_reader.py` — OPC UA CNC data reader (Fanuc 30i+)
- `sensor_diagnostics.py` — passive sensor health collector
- `background_ml.py` — ML scoring collector (APScheduler jobs)

## What this command does

1. For each collector, verify the **4 mandatory rules**:
   - **R1 — Raise in except blocks**: Every `except` clause must re-raise, log, or explicitly handle — never swallow silently
   - **R2 — Connection cleanup**: Every external connection (serial, OPC UA, PostgreSQL) must use a context manager — `with database.connection() as conn:` for PG pool (fires `putconn` on every exit path), `with serial.Serial(...) as ser:`, etc.
   - **R3 — State integrity on error**: Machine state must not default to `idle` on exception — must propagate `fault` or preserve last known state
   - **R4 — Alert on repeated failure**: If a collector fails N consecutive times, an alert must be inserted (not just logged)

2. Output an audit status table showing PASS / FAIL / WARN per rule per collector

3. For each FAIL: provide the exact file:line and corrective action

## Audit status table format

```
| Collector              | R1 Raise | R2 Cleanup | R3 State | R4 Alert |
|------------------------|----------|------------|----------|----------|
| acquisition.py         | ✅ PASS  | ✅ PASS    | ✅ PASS  | ⚠️ WARN |
| fanuc_reader.py        | ❌ FAIL  | ✅ PASS    | ⚠️ WARN  | ❌ FAIL  |
| sensor_diagnostics.py  | ✅ PASS  | ✅ PASS    | ✅ PASS  | ✅ PASS  |
| background_ml.py       | ⚠️ WARN  | ✅ PASS    | ✅ PASS  | ❌ FAIL  |
```

## Steps

1. Read `src/Application/acquisition.py`, `fanuc_reader.py`, `sensor_diagnostics.py`, `background_ml.py`
2. Grep for `except` blocks in each — verify R1 (bare `except:` or `except Exception: pass` → FAIL)
3. Grep for connection opens (`serial.Serial`, `opcua`, `database.get_connection`, `database.connection`) — verify context manager usage (`with ... as conn:`) → R2. Raw `get_connection()` + `conn.close()` is a leak under psycopg_pool + threaded uvicorn (B54 Phase C confirmed).
4. Grep for `machine_state` assignments in except blocks → R3
5. Grep for `insert_alert` calls in retry/failure branches → R4
6. Output the table + detailed findings for all FAIL/WARN items

## Skill reference

See the `audit-collectors` skill — it ships with the `ml` preset, not with the generic
payload — for detailed rule definitions and fix patterns.
