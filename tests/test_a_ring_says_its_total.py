"""R245 — a ring says its total (owner, 2026-09-27, fiches 17 and 23: « en ronds, avec la
valeur totale de chaque en étiquette »)."""
import pandas as pd

from src.dashboard.utils.charts import spend_ring


def test_a_spend_ring_writes_euros_and_cpr_and_never_a_fake_zero():
    df = pd.DataFrame({"goal": ["A", "B", "C"], "spend": [3069.0, 18.0, 0.0],
                       "results": [11366, 0, 5]})
    fig = spend_ring(df, "goal", "t")
    pie = fig.data[0]
    assert list(pie.labels) == ["A", "B"], "a slice with no spend was drawn"
    assert "CPR 0,27 €" in pie.text[0]
    assert pie.text[1].endswith("CPR —"), "no result must read « — », not 0 €"
    assert "3 087 €" in fig.layout.annotations[0].text
    assert spend_ring(pd.DataFrame({"goal": ["A"], "spend": [0.0], "results": [0]}), "goal", "t") is None
