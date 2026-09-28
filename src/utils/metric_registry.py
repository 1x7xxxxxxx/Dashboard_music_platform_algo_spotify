"""The metric registry — one canonical definition per metric, keyed by its gold object.

Type: Utility
Uses: nothing (data)
Triggers: tools/dev/gold_coverage.py (section « Le registre des métriques » of
          .claude/dev-docs/gold-coverage.md), tests/test_every_metric_is_registered.py
Persists in: nothing

R231 (2026-09-27). The owner: « une métrique = une définition canonique = une source de
vérité, réutilisée partout ; pour chaque KPI : metric_name → définition → source(s) →
formule → granularité → période → tests de qualité ».

What lives HERE is only what exists nowhere else: the metric's name, its one-line
definition, the measure it exposes, its grain, its SENSE and its default window. The
rest is COMPUTED by gold_coverage from the code — where the object is defined, what it
reads, how many surfaces read it, which tests name it — so it cannot drift from it.

The « formule » is a POINTER (`object.column`), never SQL: SQL copied here would rot the
day the view changes, and nothing would notice (code-critic, R231).

SENSE is the property this repository paid for most: `flux` (a quantity per period —
sums over time), `cumul` (a lifetime counter — never summed, only differenced), `niveau`
(a state — its last value, never summed). Drawing a `cumul` as a daily figure is the
class `cumulative-counter-drawn-as-its-own-history` (×870 on YouTube, ×306 on SoundCloud).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    name: str
    definition: str
    formula: str          # pointer: object.column(s) — never a copy of the SQL
    grain: str            # jour · mois · relevé · titre · campagne
    sense: str            # flux · cumul · niveau · attribut
    window: str           # the default period the product shows
    # R258 (critic e) — the bound its NATURE imposes, declared once: ((column, low, high),)
    # with None for an open side. Checked every evening by gold_invariants.bounds_findings.
    bounds: tuple = ()


FLUX, CUMUL, NIVEAU, ATTRIBUT = "flux", "cumul", "niveau", "attribut"

# key = the gold object (view or function) the metric is read from.
REGISTRY: dict[str, Metric] = {
    "v_s4a_song_daily": Metric(
        "streams_spotify", "Écoutes Spotify par titre et par jour (export S4A, ligne Total exclue).",
        "v_s4a_song_daily.streams", "jour × titre", FLUX, "période choisie",
        bounds=(("streams", 0, None),)),
    "v_s4a_song_measured_span": Metric(
        "spotify_measured_span", "Premier et dernier jour mesurés par titre — borne toute fenêtre.",
        "v_s4a_song_measured_span.first_measured/last_measured", "titre", ATTRIBUT, "tout"),
    "v_s4a_audience_daily": Metric(
        "spotify_audience", "Auditeurs, écoutes, sauvegardes, ajouts en playlist (artiste) et niveau d'abonnés.",
        "v_s4a_audience_daily.listeners/saves/playlist_adds (flux) · followers_level (niveau)",
        "jour", FLUX, "période choisie"),
    "v_s4a_audience_monthly": Metric(
        "spotify_audience_monthly", "La même audience agrégée au mois (abonnés : dernier niveau).",
        "v_s4a_audience_monthly", "mois", FLUX, "12 mois"),
    "v_s4a_release_cohort": Metric(
        "release_cohort", "Écoutes d'un titre par jour depuis SA sortie (âge en jours).",
        "v_s4a_release_cohort.streams", "titre × âge", FLUX, "depuis la sortie"),
    "v_s4a_release_reach": Metric(
        "release_reach", "Portée d'une sortie : écoutes cumulées à J+7 / J+28.",
        "v_s4a_release_reach", "titre", CUMUL, "fenêtres fixes"),
    "v_spotify_followers_daily": Metric(
        "spotify_followers", "Abonnés Spotify de l'artiste (niveau), CSV S4A ou API selon la source.",
        "v_spotify_followers_daily.followers", "jour", NIVEAU, "période choisie",
        bounds=(("followers", 0, None),)),
    "v_spotify_track_pi_daily": Metric(
        "spotify_popularity", "Indice de popularité Spotify (0-100) par titre.",
        "v_spotify_track_pi_daily.popularity", "jour × titre", NIVEAU, "période choisie",
        bounds=(("popularity", 0, 100),)),
    "v_platform_totals": Metric(
        "streams_all_platforms", "Écoutes par plateforme sur une fenêtre — LA porte des totaux.",
        "v_platform_totals.total", "plateforme", FLUX, "période choisie",
        bounds=(("total", 0, None),)),
    "v_platform_levels": Metric(
        "platform_levels", "Dernier niveau mesuré par plateforme (collecte partielle ≠ niveau).",
        "v_platform_levels", "plateforme", NIVEAU, "dernier relevé"),
    "gold_apple_lifetime": Metric(
        "apple_lifetime", "Écoutes et Shazams Apple à vie par titre (dernier relevé).",
        "gold_apple_lifetime(artist_id)", "titre", CUMUL, "à vie"),
    "v_apple_song_cumulative": Metric(
        "apple_cumulative", "Cumul Apple par titre et par relevé (exports d'un jour exclus).",
        "v_apple_song_cumulative.plays/shazam_count", "relevé × titre", CUMUL, "tout"),
    "v_apple_song_daily": Metric(
        "apple_daily", "Écoutes et Shazams Apple quotidiens : export d'un jour, ou écart de cumuls.",
        "v_apple_song_daily.daily_plays/daily_shazams", "jour × titre", FLUX, "période choisie"),
    "v_soundcloud_catalog_daily": Metric(
        "soundcloud_catalog", "Écoutes, likes, reposts du catalogue, avec la lisibilité par métrique.",
        "v_soundcloud_catalog_daily.plays (+ lisible)", "jour", CUMUL, "période choisie"),
    "v_soundcloud_track_daily": Metric(
        "soundcloud_track", "Les mêmes compteurs par titre.",
        "v_soundcloud_track_daily.playback_count", "jour × titre", CUMUL, "période choisie"),
    "v_soundcloud_track_latest": Metric(
        "soundcloud_track_latest", "Dernier relevé par titre SoundCloud.",
        "v_soundcloud_track_latest", "titre", CUMUL, "dernier relevé"),
    "v_youtube_video_latest": Metric(
        "youtube_video_latest", "Dernier relevé par vidéo YouTube : vues, likes, commentaires (R289).",
        "v_youtube_video_latest.view_count", "vidéo", CUMUL, "dernier relevé"),
    "v_instagram_followers_daily": Metric(
        "instagram_followers", "Abonnés, abonnements et publications Instagram.",
        "v_instagram_followers_daily.followers/follows/media", "jour", NIVEAU, "période choisie"),
    "v_instagram_media_monthly": Metric(
        "instagram_engagement", "Likes et commentaires acquis à ce jour par mois de publication.",
        "v_instagram_media_monthly.likes/comments", "mois de publication", CUMUL, "12 mois"),
    "v_hypeddit_daily": Metric(
        "hypeddit_funnel", "Visites du smart link et clics vers les plateformes, par campagne.",
        "v_hypeddit_daily.visits/clicks", "jour × campagne", FLUX, "période choisie",
        bounds=(("visits", 0, None), ("clicks", 0, None))),
    "v_meta_daily": Metric(
        "ad_spend_daily", "Dépense Meta par jour et par artiste.",
        "v_meta_daily.spend", "jour", FLUX, "période choisie",
        bounds=(("spend", 0, None), ("impressions", 0, None))),
    "v_meta_spend_totals": Metric(
        "ad_spend_total", "Dépense et résultats Meta totaux — la définition OR de « combien dépensé ».",
        "v_meta_spend_totals.spend/results", "compte", FLUX, "tout"),
    "v_meta_campaign_daily": Metric(
        "campaign_funnel", "Impressions, clics, clics lien, vues de page, clics sortants, dépense par campagne.",
        "v_meta_campaign_daily.*", "jour × campagne", FLUX, "fenêtre de campagne"),
    "v_meta_adset_daily": Metric(
        "adset_performance", "Les mêmes mesures par ensemble de publicités.",
        "v_meta_adset_daily", "jour × adset", FLUX, "période choisie"),
    "v_meta_ad_daily": Metric(
        "ad_performance", "Les mêmes mesures par publicité, avec ses réglages.",
        "v_meta_ad_daily", "jour × publicité", FLUX, "période choisie"),
    "v_meta_creative_daily": Metric(
        "creative_funnel", "Par créative : impressions, clics lien, clics sortants (mesurés ou non), dépense.",
        "v_meta_creative_daily.total_link_clicks/total_outbound", "jour × créative", FLUX, "période choisie"),
    "v_meta_engagement_daily": Metric(
        "ad_engagement", "Interactions sur les publicités (réactions, sauvegardes, partages).",
        "v_meta_engagement_daily", "jour × campagne", FLUX, "période choisie"),
    "v_meta_active_budget": Metric(
        "active_budget", "Budget quotidien des campagnes actives.",
        "v_meta_active_budget.daily_budget", "campagne", NIVEAU, "maintenant"),
    "v_meta_track_attribution": Metric(
        "campaign_track", "Le titre lié à une campagne, par lien confirmé.",
        "v_meta_track_attribution", "campagne", ATTRIBUT, "tout"),
    "v_artist_monthly_revenue": Metric(
        "revenue_gross", "Revenus BRUTS au mois : distributeurs + SACEM (répartition).",
        "v_artist_monthly_revenue.revenue_eur", "mois × source", FLUX, "12 mois"),
    "v_artist_monthly_revenue_net": Metric(
        "revenue_net", "Revenus NETS au mois, retenues déduites.",
        "v_artist_monthly_revenue_net.net_eur", "mois × source", FLUX, "12 mois"),
    "v_sacem_monthly": Metric(
        "sacem", "Relevé SACEM au mois par nature de ligne (répartition, charges, virements).",
        "v_sacem_monthly.amount", "mois × nature", FLUX, "tout"),
    "v_artist_monthly_costs": Metric(
        "costs", "Coûts saisis par l'artiste, étalés au mois (annuel /12, ponctuel dans son mois).",
        "v_artist_monthly_costs.amount_eur", "mois × catégorie", FLUX, "tout",
        bounds=(("amount_eur", 0, None),)),
    "v_artist_monthly_cashflow": Metric(
        "cashflow", "Tout l'argent au mois : revenus nets (+1) et dépenses Meta + coûts (−1).",
        "v_artist_monthly_cashflow.amount_eur × direction", "mois × source", FLUX, "tout"),
}

# Metrics read OUTSIDE the gold layer — declared, not hidden (code-critic, R231): the
# registry would otherwise lie by omission about its own scope.
TO_CONFORM: dict[str, Metric] = {
    "src/utils/mrr.py::mrr_by_plan_sql": Metric(
        "mrr", "Revenu mensuel récurrent des abonnements, locataires humains seulement.",
        "mrr_by_plan_sql() — une jointure, pas encore une vue or", "plan", NIVEAU, "maintenant"),
}


# R258 / REQ-SILVER-01 — the LAYER of every object, mechanically. Every `v_*` view the
# migrations create is GOLD and sits in REGISTRY above. The silver layer (conformed
# series, not yet a KPI) is Python, not SQL (ADR-019) : it lives in these modules, and a
# view that is neither registered nor declared here is refused by
# tests/test_every_object_has_a_layer.py.
SILVER_MODULES: tuple[str, ...] = ("src/dashboard/utils/platform_timeseries.py",)
