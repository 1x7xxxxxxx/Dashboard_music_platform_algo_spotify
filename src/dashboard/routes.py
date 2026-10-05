"""The route table of the dashboard — page key → the module whose `show()` renders it.

Type: Core
Uses: nothing (a constant)
Triggers: app._render_page (dispatch), tools/artist_first_look.py, the route tests
Persists in: nothing

R261 (owner note L356 : « un contrat de routage unique »). It was a 43-branch
`elif page == …` chain in app.py: a page added to the menu and forgotten there was
unreachable, and tests read the chain as TEXT. Values are imported as `views.<name>`
(app.py runs from src/dashboard). An alias — a retired page still routed so that old
links are not dead ends — is a second key pointing to a live module.
Guard: tests/test_every_route_resolves.py.
"""

ROUTES: dict[str, str] = {
    "home": "views.home",
    "onboarding": "views.onboarding",  # reachable from the menu too, not only from the welcome mail
    "trigger_algo": "views.trigger_algo",
    "algo_preview": "views.algo_preview",
    "meta_ads_overview": "views.meta_ads_overview",
    "meta_x_spotify": "views.meta_x_spotify",
    "spotify_s4a_combined": "views.spotify_s4a_combined",
    "hypeddit": "views.hypeddit",
    "apple_music": "views.apple_music",
    "youtube": "views.youtube",
    "soundcloud": "views.soundcloud",
    "instagram": "views.instagram",
    "data_wrapped": "views.data_wrapped",
    "imusician": "views.imusician",
    "credentials": "views.credentials",
    "process_guide": "views.onboarding_health",  # page removed 2026-09-06; its two unique sections live in onboarding_health — an old link lands where they are
    "platform_status": "views.platform_status",  # out of the menu since 2026-09-05, still routed: messages point to it
    "onboarding_health": "views.onboarding_health",
    "upload_csv": "views.credentials",  # merged into Credentials 2026-09-04; six pointers and bookmarks still target it
    "saisie_s4a": "views.saisie_s4a",
    "export_pdf": "views.export_pdf",
    "export_csv": "views.export_csv",
    "airflow_kpi": "views.airflow_kpi",
    "db_health": "views.db_health",
    "etl_logs": "views.etl_logs",
    "ml_performance": "views.ml_performance",
    "useful_links": "views.useful_links",
    "service": "views.service",
    "billing": "views.billing",
    "revenue_forecast": "views.revenue_forecast",
    "sacem": "views.sacem",
    "meta_mapping": "views.meta_mapping",
    "admin": "views.admin",
    "account": "views.account",
    "meta_creatives": "views.meta_creatives",
    "meta_breakdowns": "views.meta_breakdowns",
    "meta_cpr_optimizer": "views.meta_cpr_optimizer",
    "referral": "views.referral",
    "referral_kpi": "views.referral_admin",
    "promo_admin": "views.promo_admin",
    "upgrade": "views.upgrade",
    "usage_analytics": "views.usage_analytics",
    "alerts": "views.alerts",
    "recap": "views.home",  # alias — R379 retired the Récap page; old links land home
    "meta_campaign_settings": "views.meta_campaign_settings",  # R272 — Premium
}
