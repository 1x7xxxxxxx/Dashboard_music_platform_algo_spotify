"""R270 (note L7) — every column the importer expects says what it MEANS.

Type: Test
Uses: src/dashboard/content/csv_guides.py (CSV_GUIDES, ExpectedCsv.meanings)

Before, the guides listed column NAMES (« playlist adds », « Quantity ») and nothing said
whether `followers` was a gain or a total, or in which currency « Earnings » came.

Mutation record (2026-09-27) : the first meaning of the audience CSV removed → red. (A
cut inside an implicitly concatenated string kept the count and stayed green — the check
counts meanings, it does not read them.)
"""
from src.dashboard.content.csv_guides import CSV_GUIDES


def test_every_expected_column_has_a_meaning_not_vacuous():
    expected = [e for g in CSV_GUIDES for e in g.expected]
    assert len(expected) >= 7, "the guides are no longer read"
    bad = [f"{e.label} : {len(e.meanings)} définitions pour {len(e.columns)} colonnes"
           for e in expected if len(e.meanings) != len(e.columns)
           or not all(m.strip() for m in e.meanings)]
    assert not bad, bad
