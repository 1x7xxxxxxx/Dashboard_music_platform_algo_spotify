"""Validateurs Pydantic pour Meta Ads."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import Optional, Dict, Any
from decimal import Decimal


class MetaCampaign(BaseModel):
    """Modèle de validation pour une campagne Meta."""
    campaign_id: str = Field(..., min_length=1)
    campaign_name: str = Field(..., min_length=1, max_length=255)
    status: str = Field(..., pattern='^(ACTIVE|PAUSED|DELETED|ARCHIVED)$')
    objective: Optional[str] = None
    daily_budget: Optional[Decimal] = Field(None, ge=0)
    lifetime_budget: Optional[Decimal] = Field(None, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    collected_at: datetime
    
    @field_validator('campaign_id')
    @classmethod
    def validate_campaign_id(cls, v):
        if not v or not v.strip():
            raise ValueError("campaign_id ne peut pas être vide")
        return v.strip()


class MetaAdset(BaseModel):
    """Modèle de validation pour un adset Meta."""
    adset_id: str = Field(..., min_length=1)
    adset_name: str = Field(..., min_length=1, max_length=255)
    campaign_id: str = Field(..., min_length=1)
    status: str = Field(..., pattern='^(ACTIVE|PAUSED|DELETED|ARCHIVED)$')
    optimization_goal: Optional[str] = None
    billing_event: Optional[str] = None
    daily_budget: Optional[Decimal] = Field(None, ge=0)
    lifetime_budget: Optional[Decimal] = Field(None, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    targeting: Optional[Dict[str, Any]] = None
    collected_at: datetime


class MetaAd(BaseModel):
    """Modèle de validation pour une ad Meta."""
    ad_id: str = Field(..., min_length=1)
    ad_name: str = Field(..., min_length=1, max_length=255)
    adset_id: str = Field(..., min_length=1)
    campaign_id: str = Field(..., min_length=1)
    status: str = Field(..., pattern='^(ACTIVE|PAUSED|DELETED|ARCHIVED)$')
    creative_id: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    collected_at: datetime


class MetaInsight(BaseModel):
    """Modèle de validation pour les insights Meta."""
    ad_id: str = Field(..., min_length=1)
    date: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    spend: Decimal = Field(ge=0)
    reach: int = Field(ge=0)
    frequency: Decimal = Field(ge=0)
    cpc: Decimal = Field(ge=0)
    cpm: Decimal = Field(ge=0)
    ctr: Decimal = Field(ge=0, le=100)
    conversions: int = Field(ge=0)
    cost_per_conversion: Decimal = Field(ge=0)
    collected_at: datetime
    
    @field_validator('clicks')
    @classmethod
    def clicks_not_exceed_impressions(cls, v, info):
        """Les clicks ne peuvent pas dépasser les impressions."""
        impressions = info.data.get('impressions', 0)
        if v > impressions:
            raise ValueError(
                f"Clicks ({v}) ne peut pas dépasser impressions ({impressions})"
            )
        return v
    
    @field_validator('reach')
    @classmethod
    def reach_not_exceed_impressions(cls, v, info):
        """Le reach ne peut pas dépasser les impressions."""
        impressions = info.data.get('impressions', 0)
        if v > impressions:
            raise ValueError(
                f"Reach ({v}) ne peut pas dépasser impressions ({impressions})"
            )
        return v