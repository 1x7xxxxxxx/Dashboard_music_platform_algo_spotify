"""Unit tests for the SACEM statement parser (no DB)."""
import io

import pandas as pd
import pytest

from src.transformers.sacem_parser import (
    classify_line,
    is_sacem_statement,
    parse_sacem_xlsx,
)


def _make_xlsx(rows=None, sheet="Mon relevé de compte"):
    df = rows if rows is not None else pd.DataFrame({
        "Date": ["07/04/2026", "07/04/2026", "07/04/2026", "07/01/2026"],
        "Libellé": ["REPARTITION 674", "CSG DEDUCTIBLE 6.80% (BASE 98.25%)",
                    "Virement Caisse dEpargne", "Solde antérieur"],
        "Mouvements (€)": ["1,69", "-0,11", "-6,41", ""],
        "Solde (€)": ["6,67", "6,41", "0,00", "4,98"],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
    buf.seek(0)
    return buf


class TestClassify:
    @pytest.mark.parametrize("label,expected", [
        ("REPARTITION 674", "repartition"),
        ("Répartition 673", "repartition"),
        ("CSG DEDUCTIBLE 6.80% (BASE 98.25%)", "charge"),
        ("CRDS 0.50%", "charge"),
        ("COTISATION URSSAF VIEILLESSE 6.15% PLAFONNÉE", "charge"),
        ("CONTRIBUTION FORMATION 0.35%", "charge"),
        ("FORFAIT TVA", "tva"),
        ("Frais d'admission 2021 BAUDRY TIMOTHE", "admission"),
        ("Part sociale 2021 BAUDRY TIMOTHE", "admission"),
        ("Virement Caisse dEpargne", "payout"),
        ("Solde antérieur", "balance"),
        ("Quelque chose d'autre", "other"),
        ("", "other"),
    ])
    def test_classify(self, label, expected):
        assert classify_line(label) == expected


class TestParse:
    def test_is_sacem_statement(self):
        assert is_sacem_statement(_make_xlsx()) is True
        assert is_sacem_statement(_make_xlsx(sheet="Autre")) is False

    def test_parse_rows_and_types(self):
        rows = parse_sacem_xlsx(_make_xlsx())
        assert len(rows) == 4
        by_type = {r["line_type"] for r in rows}
        assert by_type == {"repartition", "charge", "payout", "balance"}

    def test_french_decimals_and_dates(self):
        rows = parse_sacem_xlsx(_make_xlsx())
        rep = next(r for r in rows if r["line_type"] == "repartition")
        assert rep["mouvement_eur"] == 1.69
        assert rep["line_date"].year == 2026 and rep["line_date"].month == 4
        # empty movement (Solde antérieur) → 0.0, never NaN/raise
        bal = next(r for r in rows if r["line_type"] == "balance")
        assert bal["mouvement_eur"] == 0.0 and bal["solde_eur"] == 4.98

    def test_wrong_sheet_raises(self):
        with pytest.raises(ValueError):
            parse_sacem_xlsx(_make_xlsx(sheet="Autre"))


class TestWhatMutationFoundUnpinned:
    """R509 — survivors of the first `make mutate-parsers` run, each now pinned."""

    def test_a_blank_line_mid_statement_does_not_end_the_parse(self):
        rows = parse_sacem_xlsx(_make_xlsx(pd.DataFrame({
            "Date": ["07/04/2026", "", "07/01/2026"],
            "Libellé": ["REPARTITION 674", "", "Solde antérieur"],
            "Mouvements (€)": ["1,69", "", ""],
            "Solde (€)": ["6,67", "", "4,98"],
        })))
        assert [r["line_type"] for r in rows] == ["repartition", "balance"]

    def test_a_dated_line_without_a_label_is_skipped(self):
        rows = parse_sacem_xlsx(_make_xlsx(pd.DataFrame({
            "Date": ["07/04/2026", "07/04/2026"], "Libellé": ["REPARTITION 674", ""],
            "Mouvements (€)": ["1,69", "9,99"], "Solde (€)": ["6,67", "16,66"],
        })))
        assert len(rows) == 1 and rows[0]["libelle"] == "REPARTITION 674"

    def test_an_iso_date_a_fifth_column_and_cents(self):
        rows = parse_sacem_xlsx(_make_xlsx(pd.DataFrame({
            "Date": ["2026-04-07"], "Libellé": ["URSSAF RETRAITE"],
            "Mouvements (€)": ["-1,234"], "Solde (€)": ["5,556"], "Extra": ["x"],
        })))
        assert rows[0]["line_date"].isoformat() == "2026-04-07"
        assert rows[0]["line_type"] == "charge"
        assert (rows[0]["mouvement_eur"], rows[0]["solde_eur"]) == (-1.23, 5.56)

    def test_a_label_alone_is_classified(self):
        assert classify_line("URSSAF") == "charge"
        assert classify_line("COTISATION RAAP") == "charge"

    def test_garbage_is_not_a_statement(self):
        assert is_sacem_statement(io.BytesIO(b"not an xlsx")) is False

    def test_an_unreadable_amount_reads_zero_not_one(self):
        rows = parse_sacem_xlsx(_make_xlsx(pd.DataFrame({
            "Date": ["07/04/2026"], "Libellé": ["REPARTITION 674"],
            "Mouvements (€)": ["n.c."], "Solde (€)": ["6,67"],
        })))
        assert rows[0]["mouvement_eur"] == 0.0

    def test_three_columns_is_refused_by_name(self):
        with pytest.raises(ValueError, match="≥4 columns, got 3"):
            parse_sacem_xlsx(_make_xlsx(pd.DataFrame({
                "Date": ["07/04/2026"], "Libellé": ["X"], "Mouvements (€)": ["1"]})))
