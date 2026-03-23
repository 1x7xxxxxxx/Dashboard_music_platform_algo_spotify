"""Tests unitaires — Pydantic validators Meta Ads."""
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

    def test_targeting_optional(self):
        a = self._valid(targeting={"countries": ["FR"]})
        assert a.targeting == {"countries": ["FR"]}


# =============================================================================
# MetaAd
# =============================================================================

class TestMetaAd:

    def _valid(self, **overrides):
        base = dict(
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
