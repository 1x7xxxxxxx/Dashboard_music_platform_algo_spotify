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
