"""The admin « all artists » money door, as SQL — shared by the page and the nightly check.

Type: Utility
Uses: src/utils/tenant_kind.py (the one « not a real tenant » predicate)
Triggers: src/dashboard/utils/treasury_chart.load_cashflow (admin branch),
          src/utils/gold_invariants.py (fleet_cashflow_is_the_sum_of_humans)
Persists in: nothing

R226 (2026-09-27). The admin treasury summed the sandbox, which mirrors artist 1 byte
for byte, and doubled (R220). The test that caught it runs on test data; the nightly
invariant runs THIS SQL on production data and compares it with the per-tenant sum over
human tenants. It lives here and not in the dashboard so that the Airflow worker never
imports a Streamlit module (code-critic, R226).
"""
from __future__ import annotations

from src.utils.tenant_kind import NON_HUMAN_TENANT

# « All artists » means the HUMAN ones. An inactive human keeps its money history, so
# the predicate is « not canary, not sandbox », not « active ».
FLEET_CASHFLOW_SQL = f"""SELECT year, month, flux, source, SUM(amount_eur) AS amount_eur, direction
           FROM v_artist_monthly_cashflow
           WHERE artist_id IN (SELECT id FROM saas_artists WHERE NOT {NON_HUMAN_TENANT})
           GROUP BY year, month, flux, source, direction"""
