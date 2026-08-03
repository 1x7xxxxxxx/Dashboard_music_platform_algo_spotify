---
rex: []
---

Audit API routes in api.py against the endpoints documentation.

## What to do

### Step 1 — Extract documented endpoints
Read `.claude/dev-docs/api/endpoints.md`.
Extract all documented routes: method + path (e.g. GET /data/latest, POST /predict).

### Step 2 — Extract implemented endpoints
Read `src/Application/api.py`.
Extract all route decorators: @app.get, @app.post, @app.put, @app.delete, @app.patch.
Include the path string from each decorator.

### Step 3 — Compare
For each implemented route:
- ✅ if documented in endpoints.md
- ❌ if implemented but missing from documentation

For each documented route:
- ✅ if found in api.py
- ❌ if documented but not implemented (ghost endpoint)

### Step 4 — Check response schemas
For the 5 most recently modified endpoints (from DEVLOG.md last entries if available):
- Verify the response fields listed in endpoints.md match the actual dict/model returned in api.py
- Flag mismatches as ⚠️

## Output format

Summary line: "X routes in api.py | Y routes in endpoints.md | Z undocumented | W ghost endpoints"
Then the checklist grouped by: Undocumented routes / Ghost endpoints / In sync.
End with recommended action if issues found.

## When to use

- After adding new endpoints
- Before sharing API docs with an external team (HMI C++ bridge, PLC integrator)
- As part of pre-deployment checklist (Phase 0 before IPC site visit)
