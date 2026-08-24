"""Validateurs Pydantic pour Meta Ads — appelés par `_MetaUpsertMixin`.

Type: Sub
Uses: pydantic
Triggers: src/collectors/_meta_upsert.py (`_upsert_config`, `_persist_insights`)
Persists in: rien — refuse ou laisse passer

R47, tranché le 2026-08-24 : **branchés**, après correction.

Ces quatre modèles existaient depuis des mois sans un seul appelant de production
— seul `tests/test_validators.py` les importait. La ROADMAP les décrivait comme
« exactement la forme des payloads que `_meta_upsert.py` écrit ». Ils ne l'étaient
pas, et les brancher tels quels aurait **arrêté la collecte** :

  * aucun ne déclarait `artist_id`, que tout payload porte — donc la couche censée
    protéger l'intégrité des données ne regardait pas le champ du locataire, le seul
    dont ce dépôt ait réellement souffert ;
  * `status` était obligatoire alors que le collecteur écrit `c.get('status')`, qui
    peut être `None` sur une campagne archivée ;
  * `MetaInsight` exigeait dix métriques non nulles avec `ge=0` : une insight sans
    `cpc` (cas nominal d'une campagne d'engagement) aurait levé chaque nuit.

C'est le motif que R48 décrit : un module écrit, testé, décrit dans
l'architecture, et que rien n'exécute. Le test passait *parce que* rien ne
l'exécutait — il vérifiait le modèle contre des payloads inventés par le test,
jamais contre ceux du collecteur.

Ce que ces modèles refusent maintenant, et pourquoi ça vaut d'être refusé :
identifiant vide, locataire absent, budget négatif, statut hors de l'énumération
Meta, métrique négative. Chacun produit une ligne en base qu'aucune vue ne peut
rattraper.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Les statuts que Meta rend sur le champ `status` d'un objet (à ne pas confondre
# avec `effective_status`, qui porte en plus les états HÉRITÉS — CAMPAIGN_PAUSED,
# ADSET_PAUSED — et sert de FILTRE à la requête, jamais de valeur stockée).
_OBJECT_STATUS = '^(ACTIVE|PAUSED|DELETED|ARCHIVED)$'

# `extra='ignore'` est explicite, pas subi : les payloads d'adset portent quinze
# colonnes de ciblage que ces modèles n'ont pas à connaître. Le contrat est
# « ces champs-là doivent être justes », pas « il n'y en a pas d'autres ».
_CONFIG = ConfigDict(extra='ignore')


class _TenantScoped(BaseModel):
    """Tout ce qu'on écrit nomme son locataire. Le reste hérite d'ici.

    `artist_id` obligatoire n'est pas de la rigueur décorative : une ligne écrite
    sans locataire laisse la base choisir le propriétaire, et c'est exactement ce
    qui a fait écrire des mois de `track_popularity_history` sous l'admin.
    """

    model_config = _CONFIG

    artist_id: int = Field(..., ge=1)
    # Compte publicitaire d'origine (R53). `None` sur l'historique d'avant la
    # migration 077, obligatoire dans les faits dès que le collecteur tourne.
    ad_account_id: Optional[str] = None
    collected_at: datetime


class MetaCampaign(_TenantScoped):
    """Une campagne, telle que `_fetch_campaigns` la construit."""

    campaign_id: str = Field(..., min_length=1)
    campaign_name: str = Field(..., min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern=_OBJECT_STATUS)
    objective: Optional[str] = None
    daily_budget: Optional[Decimal] = Field(None, ge=0)
    lifetime_budget: Optional[Decimal] = Field(None, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None

    @field_validator('campaign_id', 'campaign_name')
    @classmethod
    def _not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("valeur vide")
        return v.strip()


class MetaAdset(_TenantScoped):
    """Un ad set. Les quinze colonnes de ciblage sont ignorées, pas interdites."""

    adset_id: str = Field(..., min_length=1)
    adset_name: str = Field(..., min_length=1, max_length=255)
    campaign_id: str = Field(..., min_length=1)
    status: Optional[str] = Field(None, pattern=_OBJECT_STATUS)
    optimization_goal: Optional[str] = None
    billing_event: Optional[str] = None
    daily_budget: Optional[Decimal] = Field(None, ge=0)
    lifetime_budget: Optional[Decimal] = Field(None, ge=0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    # Une CHAÎNE JSON, pas un dict : `_fetch_adsets` fait `json.dumps(tgt_dict)`
    # avant d'écrire, parce que la colonne est du texte et que les attributs de
    # ciblage utiles sont déjà éclatés en colonnes propres (countries, gender…).
    # Le modèle déclarait `Dict[str, Any]` — troisième divergence trouvée en
    # branchant, et celle qui aurait fait échouer la collecte dès la première nuit.
    targeting: Optional[str] = None


class MetaAd(_TenantScoped):
    """Une publicité."""

    ad_id: str = Field(..., min_length=1)
    ad_name: str = Field(..., min_length=1, max_length=255)
    adset_id: str = Field(..., min_length=1)
    campaign_id: str = Field(..., min_length=1)
    status: Optional[str] = Field(None, pattern=_OBJECT_STATUS)
    creative_id: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None


class MetaInsight(_TenantScoped):
    """Une ligne de `meta_insights` (maille publicité × jour).

    Les métriques sont **facultatives** : Meta ne rend pas `cpc` sur un objectif
    d'engagement, ni `cost_per_conversion` sans conversion. Ce qui est contrôlé,
    c'est leur SIGNE et leur cohérence entre elles — une dépense négative ou un
    reach supérieur aux impressions ne sont pas des absences, ce sont des données
    fausses, et aucune vue ne peut les rattraper une fois écrites.
    """

    ad_id: str = Field(..., min_length=1)
    date: date
    impressions: Optional[int] = Field(None, ge=0)
    clicks: Optional[int] = Field(None, ge=0)
    spend: Optional[Decimal] = Field(None, ge=0)
    reach: Optional[int] = Field(None, ge=0)
    frequency: Optional[Decimal] = Field(None, ge=0)
    cpc: Optional[Decimal] = Field(None, ge=0)
    cpm: Optional[Decimal] = Field(None, ge=0)
    ctr: Optional[Decimal] = Field(None, ge=0, le=100)
    conversions: Optional[int] = Field(None, ge=0)
    cost_per_conversion: Optional[Decimal] = Field(None, ge=0)

    @field_validator('clicks', 'reach')
    @classmethod
    def _not_more_than_impressions(cls, v, info):
        """Comparaison seulement quand les DEUX valeurs existent.

        La version précédente lisait `info.data.get('impressions', 0)` : une
        insight sans impressions faisait donc échouer tout clic non nul contre un
        zéro qui n'était pas une mesure mais un défaut d'écriture.
        """
        impressions = info.data.get('impressions')
        if v is not None and impressions is not None and v > impressions:
            raise ValueError(
                f"{info.field_name} ({v}) dépasse impressions ({impressions})")
        return v
