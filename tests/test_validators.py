"""Tests unitaires — Pydantic validators Meta Ads.

R47 (2026-08-24) : ces fixtures ont été refaites, et le fait qu'il ait fallu les
refaire EST le constat. Elles construisaient des payloads sans `artist_id` — donc
des payloads que le collecteur n'écrit jamais — et passaient au vert depuis des
mois contre des modèles qu'aucun code de production n'appelait. Un test vert sur
une forme inventée ne dit rien de la forme réelle.

L'anti-dérive est `test_validators_against_real_payloads.py` : il valide les
modèles contre la sortie des vraies méthodes de fetch du collecteur, avec la SDK
stub. Ce fichier-ci garde les règles ; celui-là garde la CORRESPONDANCE.
"""
from datetime import datetime, date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.models.meta_ads_validators import MetaCampaign, MetaAdset, MetaAd, MetaInsight


NOW = datetime(2024, 6, 1, 12, 0, 0)
TODAY = date(2024, 6, 1)


# =============================================================================
# MetaCampaign
# =============================================================================

class TestMetaCampaign:

    def _valid(self, **overrides):
        base = dict(
            artist_id=1,
            campaign_id="123",
            campaign_name="Test Campaign",
            status="ACTIVE",
            collected_at=NOW,
        )
        base.update(overrides)
        return MetaCampaign(**base)

    def test_valid_campaign(self):
        c = self._valid()
        assert c.campaign_id == "123"
        assert c.status == "ACTIVE"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            self._valid(status="RUNNING")

    def test_empty_campaign_id_raises(self):
        with pytest.raises(ValidationError):
            self._valid(campaign_id="   ")

    def test_optional_fields_default_none(self):
        c = self._valid()
        assert c.objective is None
        assert c.daily_budget is None

    def test_negative_budget_raises(self):
        with pytest.raises(ValidationError):
            self._valid(daily_budget=Decimal("-10"))

    @pytest.mark.parametrize("status", ["ACTIVE", "PAUSED", "DELETED", "ARCHIVED"])
    def test_all_valid_statuses(self, status):
        c = self._valid(status=status)
        assert c.status == status


# =============================================================================
# MetaAdset
# =============================================================================

class TestMetaAdset:

    def _valid(self, **overrides):
        base = dict(
            artist_id=1,
            adset_id="456",
            adset_name="Test Adset",
            campaign_id="123",
            status="PAUSED",
            collected_at=NOW,
        )
        base.update(overrides)
        return MetaAdset(**base)

    def test_valid_adset(self):
        a = self._valid()
        assert a.adset_id == "456"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            self._valid(status="LIVE")

    def test_targeting_is_a_json_string_not_a_dict(self):
        """`_fetch_adsets` écrit `json.dumps(...)` : la colonne est du texte."""
        a = self._valid(targeting='{"geo_locations": {"countries": ["FR"]}}')
        assert isinstance(a.targeting, str)

    def test_targeting_may_be_absent(self):
        assert self._valid(targeting=None).targeting is None


# =============================================================================
# MetaAd
# =============================================================================

class TestMetaAd:

    def _valid(self, **overrides):
        base = dict(
            artist_id=1,
            ad_id="789",
            ad_name="Test Ad",
            adset_id="456",
            campaign_id="123",
            status="ACTIVE",
            collected_at=NOW,
        )
        base.update(overrides)
        return MetaAd(**base)

    def test_valid_ad(self):
        a = self._valid()
        assert a.ad_id == "789"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            self._valid(status="ON")


# =============================================================================
# MetaInsight
# =============================================================================

class TestMetaInsight:

    def _valid(self, **overrides):
        base = dict(
            artist_id=1,
            ad_id="789",
            date=TODAY,
            impressions=1000,
            clicks=50,
            spend=Decimal("10.00"),
            reach=800,
            frequency=Decimal("1.25"),
            cpc=Decimal("0.20"),
            cpm=Decimal("10.00"),
            ctr=Decimal("5.0"),
            conversions=5,
            cost_per_conversion=Decimal("2.00"),
            collected_at=NOW,
        )
        base.update(overrides)
        return MetaInsight(**base)

    def test_valid_insight(self):
        i = self._valid()
        assert i.impressions == 1000
        assert i.clicks == 50

    def test_clicks_exceed_impressions_raises(self):
        with pytest.raises(ValidationError):
            self._valid(impressions=100, clicks=200)

    def test_reach_exceed_impressions_raises(self):
        with pytest.raises(ValidationError):
            self._valid(impressions=100, reach=200)

    def test_negative_spend_raises(self):
        with pytest.raises(ValidationError):
            self._valid(spend=Decimal("-1.00"))

    def test_ctr_above_100_raises(self):
        with pytest.raises(ValidationError):
            self._valid(ctr=Decimal("101.0"))

    def test_zero_values_valid(self):
        i = self._valid(clicks=0, reach=0, conversions=0, spend=Decimal("0"))
        assert i.clicks == 0

    def test_impressions_zero_clicks_zero_valid(self):
        """Cas réel : 0 impressions, 0 clicks."""
        i = self._valid(impressions=0, clicks=0, reach=0)
        assert i.impressions == 0


# =============================================================================
# Le locataire — la raison d'être du branchement (R47)
# =============================================================================

class TestTenantIsMandatory:
    """Un payload sans locataire laisse la base choisir le propriétaire.

    C'est le seul défaut dont ce dépôt ait réellement souffert
    (`track_popularity_history`, des mois écrits sous l'admin). Les quatre modèles
    l'ignoraient : ils validaient tout SAUF le champ qui compte.
    """

    @pytest.mark.parametrize("model,payload", [
        (MetaCampaign, dict(campaign_id="1", campaign_name="C", collected_at=NOW)),
        (MetaAdset, dict(adset_id="1", adset_name="A", campaign_id="1", collected_at=NOW)),
        (MetaAd, dict(ad_id="1", ad_name="A", adset_id="1", campaign_id="1",
                      collected_at=NOW)),
        (MetaInsight, dict(ad_id="1", date=TODAY, collected_at=NOW)),
    ], ids=["campaign", "adset", "ad", "insight"])
    def test_a_payload_without_a_tenant_is_refused(self, model, payload):
        with pytest.raises(ValidationError):
            model(**payload)

    @pytest.mark.parametrize("model,payload", [
        (MetaCampaign, dict(artist_id=1, campaign_id="1", campaign_name="C",
                            collected_at=NOW)),
        (MetaInsight, dict(artist_id=1, ad_id="1", date=TODAY, collected_at=NOW)),
    ], ids=["campaign", "insight"])
    def test_metrics_and_status_may_be_absent(self, model, payload):
        """Meta ne rend pas `cpc` sur un objectif d'engagement, ni `status` sur
        certaines campagnes archivées. Exiger ces champs aurait arrêté la
        collecte chaque nuit — c'est ce que faisaient les modèles d'origine."""
        assert model(**payload) is not None


# =============================================================================
# L'anti-dérive — R47 : le branchement lui-même
# =============================================================================

def test_the_collector_actually_calls_the_validators():
    """Garde de la classe `layer-written-but-never-wired`.

    Le défaut d'origine n'était pas dans les modèles : c'est qu'aucun code de
    production ne les importait, pendant que `CLAUDE.md` annonçait `models/` comme
    une couche de l'architecture et que ce fichier passait au vert. Un test qui ne
    vérifie que les règles laisserait débrancher la couche sans un rouge.

    AST, pas une recherche de texte : un import mentionné dans un commentaire ou
    une docstring satisferait un `grep` sans rien exécuter.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("src/collectors/_meta_upsert.py")
                     .read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "src.models.meta_ads_validators"
        for alias in node.names
    }
    assert {"MetaCampaign", "MetaAdset", "MetaAd", "MetaInsight"} <= imported, (
        "les validateurs ne sont plus importés par le collecteur : la couche est "
        f"redevenue décorative (importés : {sorted(imported)})"
    )

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_validate" in called, "les modèles sont importés mais jamais appliqués"
