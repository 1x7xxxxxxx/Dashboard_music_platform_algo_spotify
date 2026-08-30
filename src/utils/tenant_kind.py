"""What kind of tenant a row is, expressed once so the SQL cannot drift apart.

Type: Utility
Uses: nothing
Depends on: saas_artists.is_canary, saas_artists.is_sandbox
Persists in: nothing

Three kinds
-----------
=========== =========================== ================= =====================
kind        what it is                  identity guard    counted / alerted on
=========== =========================== ================= =====================
real        a customer                  enforced          yes
canary      our monitoring robot        enforced          no
sandbox     our own throwaway rehearsal **exempt**        no
=========== =========================== ================= =====================

The sandbox exemption is the dangerous one, so it is granted by its OWN flag rather
than folded into `is_canary`: the production canary uses public artist ids and must
keep the guard, and widening a permission to a tenant that never asked for it is how
a guard stops meaning anything.

Why a shared constant rather than the literal in each query
----------------------------------------------------------
Before this module, "not a real tenant" was written as `COALESCE(is_canary, FALSE) =
FALSE` in two unrelated files. Adding a second flag meant finding both — and one of
them was inside an f-string in a counter nobody thinks about while adding a column.
`tests/test_a_tenant_flag_is_applied_everywhere.py` fails if a query filters on one
flag without the other.
"""
from __future__ import annotations

# A tenant we operate ourselves — never a customer, never in public counts.
NON_HUMAN_TENANT = "(COALESCE(is_canary, FALSE) OR COALESCE(is_sandbox, FALSE))"

# The complement, for the counters that answer "how many artists use streaMLytics".
HUMAN_TENANTS = f"active = TRUE AND NOT {NON_HUMAN_TENANT}"

# Appended to a WHERE that already has a condition, when a check is onboarding-shaped
# and would otherwise raise on a tenant nobody is onboarding.
EXCLUDE_NON_HUMAN = f" AND NOT {NON_HUMAN_TENANT}"
