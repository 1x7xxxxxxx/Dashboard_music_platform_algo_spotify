# Couverture de la couche or

<!-- GÉNÉRÉ par `tools/dev/gold_coverage.py` — toute édition à la main est perdue à la prochaine exécution. `make gold-coverage` -->

Ce document répond à une seule question, pour chaque figure, chaque tuile et chaque figure du PDF : **quelle donnée dessine-t-elle, et passe-t-elle par la couche or ?**

Il est écrit par une machine qui lit `migrations/*.sql`, `init_db.sql` et l'AST de `src/`. Elle n'exécute rien, ne lit aucune base, et **ne porte aucun horodatage** — deux exécutions sur le même arbre rendent exactement les mêmes octets, ce qui est la seule façon pour `--check` de dire quelque chose.

## Les onze axes, et où chacun est répondu

Un inventaire de figures ne suffit pas : il décrit un état sans dire ce qui le tient, et c'est l'état qui dérive. Chaque axe ci-dessous a sa section, et sa colonne de trous.

| # | axe | la question | où |
|---|---|---|---|
| 1 | Graphique | quelle donnée trace-t-il, d'où vient-elle ? | [Les figures d'écran](#les-figures-décran) |
| 2 | Tuile (`.metric`) | quel nombre affirme-t-elle, par quelle porte ? | [Les tuiles](#les-tuiles) |
| 3 | Plateforme | quelles vues or la définissent, et que reste-t-il de brut ? | [Les plateformes](#les-plateformes) |
| 4 | Vue or | qui la lit — et depuis quel processus ? | [La couche or](#la-couche-or) |
| 5 | Porte Python | quelle vue lit-elle ? porte-t-elle une règle que la vue n'a pas ? | [La couche or](#la-couche-or) (colonne « lit ») |
| 6 | Figure PDF | le document envoyé à des tiers lit-il les mêmes définitions ? | [Les figures du PDF](#les-figures-du-pdf) |
| 7 | Classe d'erreur | le garde qu'elle nomme existe-t-il encore ? | [Les classes d'erreur](#les-classes-derreur) |
| 8 | Garde | a-t-il une trace de mutation — a-t-il été VU rouge ? | [Les cliquets](#les-cliquets) |
| 9 | Cliquet | sa valeur est-elle serrée, et a-t-il un test de non-vacuité ? | [Les cliquets](#les-cliquets) |
| 10 | Étape CI | qu'est-ce qui bloque, qu'est-ce qui ne fait que rapporter ? | [Les étapes de la CI](#les-étapes-de-la-ci) |
| 11 | Trou | figure sans source · classe sans garde · cliquet sans non-vacuité | [Ce qui n'est atteint par rien](#ce-qui-nest-atteint-par-rien) et les chiffres gelés |

## Ce que ce document ne sait pas

Lis cette section avant les tableaux. Un aveu placé après la donnée est un aveu que personne ne lit.

Une attribution n'est publiée que s'il existe un **chemin def-use prouvé** entre une lecture SQL et la surface. Quand il n'y en a pas, la colonne « source établie » vaut `—` et la ligne porte un motif. Elle n'est **jamais** remplie par ce que la fonction lit à côté : cette colonne-là existe, elle est la dernière, et son en-tête dit qu'elle ne prouve rien.

| motif | ce qu'il veut dire | occurrences |
|---|---|---|
| `sql-dynamique` | requête ou table assemblée hors littéral — indécidable sans exécuter | 17 |
| `identifiant-non-résolu` | un nom capté dans un FROM qui n'existe ni en migration ni dans init_db.sql (CTE, alias, sous-requête) — écarté plutôt que publié | 2 |
| `appelants-multiples` | rendu partagé par plus de trois appelants : un site, N jeux de données | 4 |
| `profondeur` | chaîne de plus de 3 sauts — plafond MESURÉ : le cran suivant n'apporte rien | 37 |
| `sans-appelant` | fonction dont aucun appel n'est résoluble statiquement | 13 |
| `clé-à-l-exécution` | argument passé par **kwargs, partial, ou conteneur indexé par une variable | 18 |
| `receveur-inconnu` | `X.metric(...)` où X n'est lié ni à st.columns ni à st.tabs — compté, pas deviné | 1 |
| `sans-retour` | fonction traversée qui ne retourne rien d'attribuable | 0 |

Cinq mots de confiance, et rien d'autre :

- **directe** — la tranche est restée dans une fonction et a atteint un exécuteur à SQL littéral, ou une porte.
- **portée (N sauts)** — N relèvements de paramètre, **chacun vers un appelant unique**.
- **plusieurs amonts** — plusieurs définitions ou plusieurs appelants : l'union est listée, aucune n'est choisie.
- **hors base** — la tranche s'est terminée proprement sans lecture de base (CSV déposé, artefact ML, appel REST). **Ce n'est pas un échec.**
- **indéterminée** — la tranche est tronquée. Toujours accompagnée d'un motif, et triée **en tête** de son tableau.

## La couche or

| objet | genre | définie par | lit | surfaces qui la lisent | définitions supplantées |
|---|---|---|---|---|---|
| `gold_apple_lifetime` | fonction | `migrations/114_gold_apple_lifetime_per_song.sql` | — | 8 | `migrations/102_gold_apple.sql` · `migrations/103_gold_apple_metric.sql` · `migrations/113_gold_apple_absence_is_not_zero.sql` · `migrations/114_gold_apple_lifetime_per_song.sql` |
| `v_apple_song_cumulative` | vue | `migrations/142_apple_daily_from_single_day_exports.sql` | `apple_songs_history` · `apple_songs_performance` | 4 | `migrations/131_gold_apple_song_series.sql` |
| `v_apple_song_daily` | vue | `migrations/142_apple_daily_from_single_day_exports.sql` | `apple_songs_performance` · `v_apple_song_cumulative` | 4 | `migrations/131_gold_apple_song_series.sql` |
| `v_artist_monthly_cashflow` | vue | `migrations/133_gold_artist_cashflow.sql` | `v_artist_monthly_costs` · `v_artist_monthly_revenue_net` · `v_meta_daily` | 18 | — |
| `v_artist_monthly_costs` | vue | `migrations/133_gold_artist_cashflow.sql` | `artist_cost_entries` | 1 | — |
| `v_artist_monthly_revenue` | vue | `init_db.sql` | `distrokid_monthly_revenue` · `imusician_monthly_revenue` · `sacem_statement` | 14 | `migrations/056_v_artist_monthly_revenue.sql` · `migrations/111_gold_sacem_monthly.sql` |
| `v_artist_monthly_revenue_net` | vue | `migrations/115_gold_revenue_gross_and_net.sql` | `distrokid_monthly_revenue` · `imusician_monthly_revenue` · `v_sacem_monthly` | 1 | — |
| `v_hypeddit_daily` | vue | `migrations/106_gold_remaining_grains.sql` | `hypeddit_daily_stats` | 15 | — |
| `v_instagram_followers_daily` | vue | `migrations/121_gold_instagram_followers.sql` | `instagram_daily_stats` | 8 | — |
| `v_instagram_media_monthly` | vue | `migrations/106_gold_remaining_grains.sql` | `instagram_media` | 4 | — |
| `v_meta_active_budget` | vue | `migrations/110_gold_meta_active_budget.sql` | `meta_campaigns` | 10 | — |
| `v_meta_ad_daily` | vue | `migrations/140_gold_meta_engagement_and_ad_settings.sql` | `meta_ads` · `meta_campaigns` · `meta_insights` | 1 | — |
| `v_meta_adset_daily` | vue | `migrations/108_gold_meta_creative_account_and_adset.sql` | `meta_ads` · `meta_adsets` · `meta_insights` | 2 | — |
| `v_meta_campaign_daily` | vue | `migrations/109_gold_meta_campaign_daily.sql` | `meta_insights_performance` · `meta_insights_performance_day` | 24 | — |
| `v_meta_creative_daily` | vue | `migrations/139_meta_ad_grain_funnel_stages.sql` | `meta_ads` · `meta_adsets` · `meta_campaigns` · `meta_insights` | 15 | `migrations/106_gold_remaining_grains.sql` · `migrations/108_gold_meta_creative_account_and_adset.sql` |
| `v_meta_daily` | vue | `migrations/106_gold_remaining_grains.sql` | `meta_insights_performance_day` | 25 | — |
| `v_meta_engagement_daily` | vue | `migrations/140_gold_meta_engagement_and_ad_settings.sql` | `meta_insights_engagement` · `meta_insights_engagement_day` | 4 | — |
| `v_meta_spend_totals` | vue | `migrations/101_gold_meta_spend.sql` | `meta_insights_performance_day` | 2 | — |
| `v_meta_track_attribution` | vue | `migrations/116_gold_meta_track_attribution.sql` | `track_platform_link` · `v_meta_campaign_daily` | 1 | — |
| `v_platform_levels` | vue | `migrations/112_gold_partial_collection_is_not_a_level.sql` | `s4a_song_timeline` · `soundcloud_tracks_daily` · `youtube_video_stats` | 3 | `migrations/104_gold_platform_levels.sql` |
| `v_platform_totals` | vue | `migrations/107_gold_soundcloud_track_latest.sql` | `apple_songs_performance` · `gold_apple_lifetime` · `v_s4a_song_daily` · `v_soundcloud_track_latest` · `youtube_video_stats` | 15 | `migrations/097_v_platform_totals.sql` · `migrations/102_gold_apple.sql` · `migrations/103_gold_apple_metric.sql` |
| `v_s4a_audience_daily` | vue | `migrations/117_gold_s4a_audience.sql` | `s4a_audience` | 6 | — |
| `v_s4a_audience_monthly` | vue | `migrations/117_gold_s4a_audience.sql` | `v_s4a_audience_daily` | 1 | — |
| `v_s4a_release_cohort` | vue | `migrations/119_gold_s4a_release_cohort.sql` | `track_platform_link` · `track_release_reference` · `v_s4a_song_daily` | 2 | — |
| `v_s4a_release_reach` | vue | `migrations/119_gold_s4a_release_cohort.sql` | `track_platform_link` · `track_release_reference` · `v_s4a_release_cohort` · `v_s4a_song_daily` | 1 | — |
| `v_s4a_song_daily` | vue | `migrations/105_gold_s4a_song_daily.sql` | `s4a_song_timeline` | 35 | — |
| `v_s4a_song_measured_span` | vue | `migrations/118_gold_s4a_song_span.sql` | `v_s4a_song_daily` | 3 | — |
| `v_sacem_monthly` | vue | `migrations/111_gold_sacem_monthly.sql` | `sacem_statement` | 3 | — |
| `v_soundcloud_catalog_daily` | vue | `migrations/138_gold_soundcloud_catalog_per_metric_readability.sql` | `soundcloud_tracks_daily` | 3 | `migrations/132_gold_soundcloud_daily.sql` |
| `v_soundcloud_track_daily` | vue | `migrations/132_gold_soundcloud_daily.sql` | `soundcloud_tracks_daily` · `v_soundcloud_catalog_daily` | 6 | — |
| `v_soundcloud_track_latest` | vue | `migrations/107_gold_soundcloud_track_latest.sql` | `soundcloud_tracks_daily` | 5 | — |
| `v_spotify_followers_daily` | vue | `migrations/120_gold_spotify_followers.sql` | `artist_history` · `saas_artists` · `v_s4a_audience_daily` | 1 | — |
| `v_spotify_track_pi_daily` | vue | `migrations/130_gold_spotify_track_popularity.sql` | `track_platform_link` · `track_popularity_history` · `track_release_reference` | 7 | — |

## Le registre des métriques

Une métrique = une définition = une source. Écrit à la main dans `tools/dev/metric_registry.py` : le nom, la définition, la mesure, la granularité, le **sens** (flux se somme ; cumul se différencie, jamais ne se somme ; niveau se lit à sa dernière valeur) et la période. Calculé ici depuis le code : la source, les surfaces, les tests qui la nomment. La formule est un POINTEUR vers la vue, jamais une copie de son SQL.

| métrique | définition | source | formule | granularité | sens | période | surfaces | tests qui la nomment |
|---|---|---|---|---|---|---|---|---|
| **active_budget** | Budget quotidien des campagnes actives. | `v_meta_active_budget` | `v_meta_active_budget.daily_budget` | campagne | niveau | maintenant | 10 | **0** |
| **ad_engagement** | Interactions sur les publicités (réactions, sauvegardes, partages). | `v_meta_engagement_daily` | `v_meta_engagement_daily` | jour × campagne | flux | période choisie | 4 | 2 — `test_a_join_never_multiplies_the_grain.py` … |
| **ad_performance** | Les mêmes mesures par publicité, avec ses réglages. | `v_meta_ad_daily` | `v_meta_ad_daily` | jour × publicité | flux | période choisie | 1 | 2 — `test_a_join_never_multiplies_the_grain.py` … |
| **ad_spend_daily** | Dépense Meta par jour et par artiste. | `v_meta_daily` | `v_meta_daily.spend` | jour | flux | période choisie | 25 | 8 — `test_a_campaign_figure_carries_its_date.py` … |
| **ad_spend_total** | Dépense et résultats Meta totaux — la définition OR de « combien dépensé ». | `v_meta_spend_totals` | `v_meta_spend_totals.spend/results` | compte | flux | tout | 2 | 2 — `test_the_gold_layer_agrees_with_itself.py` … |
| **adset_performance** | Les mêmes mesures par ensemble de publicités. | `v_meta_adset_daily` | `v_meta_adset_daily` | jour × adset | flux | période choisie | 2 | 1 — `test_an_account_filter_names_one_column.py` |
| **apple_cumulative** | Cumul Apple par titre et par relevé (exports d'un jour exclus). | `v_apple_song_cumulative` | `v_apple_song_cumulative.plays/shazam_count` | relevé × titre | cumul | tout | 4 | 3 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **apple_daily** | Écoutes et Shazams Apple quotidiens : export d'un jour, ou écart de cumuls. | `v_apple_song_daily` | `v_apple_song_daily.daily_plays/daily_shazams` | jour × titre | flux | période choisie | 4 | 2 — `test_a_daily_apple_export_gives_daily_shazams.py` … |
| **apple_lifetime** | Écoutes et Shazams Apple à vie par titre (dernier relevé). | `gold_apple_lifetime` | `gold_apple_lifetime(artist_id)` | titre | cumul | à vie | 8 | 4 — `test_a_gold_rule_is_declarative.py` … |
| **campaign_funnel** | Impressions, clics, clics lien, vues de page, clics sortants, dépense par campagne. | `v_meta_campaign_daily` | `v_meta_campaign_daily.*` | jour × campagne | flux | fenêtre de campagne | 24 | 6 — `test_a_join_never_multiplies_the_grain.py` … |
| **campaign_track** | Le titre lié à une campagne, par lien confirmé. | `v_meta_track_attribution` | `v_meta_track_attribution` | campagne | attribut | tout | 1 | **0** |
| **cashflow** | Tout l'argent au mois : revenus nets (+1) et dépenses Meta + coûts (−1). | `v_artist_monthly_cashflow` | `v_artist_monthly_cashflow.amount_eur × direction` | mois × source | flux | tout | 18 | 5 — `test_a_break_even_is_a_date_not_a_crash.py` … |
| **costs** | Coûts saisis par l'artiste, étalés au mois (annuel /12, ponctuel dans son mois). | `v_artist_monthly_costs` | `v_artist_monthly_costs.amount_eur` | mois × catégorie | flux | tout | 1 | **0** |
| **creative_funnel** | Par créative : impressions, clics lien, clics sortants (mesurés ou non), dépense. | `v_meta_creative_daily` | `v_meta_creative_daily.total_link_clicks/total_outbound` | jour × créative | flux | période choisie | 15 | 5 — `test_a_creative_funnel_never_widens.py` … |
| **hypeddit_funnel** | Visites du smart link et clics vers les plateformes, par campagne. | `v_hypeddit_daily` | `v_hypeddit_daily.visits/clicks` | jour × campagne | flux | période choisie | 15 | 5 — `test_a_failed_read_is_not_an_absence.py` … |
| **instagram_engagement** | Likes et commentaires acquis à ce jour par mois de publication. | `v_instagram_media_monthly` | `v_instagram_media_monthly.likes/comments` | mois de publication | cumul | 12 mois | 4 | 4 — `test_a_failed_read_is_not_an_absence.py` … |
| **instagram_followers** | Abonnés, abonnements et publications Instagram. | `v_instagram_followers_daily` | `v_instagram_followers_daily.followers/follows/media` | jour | niveau | période choisie | 8 | 1 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` |
| **platform_levels** | Dernier niveau mesuré par plateforme (collecte partielle ≠ niveau). | `v_platform_levels` | `v_platform_levels` | plateforme | niveau | dernier relevé | 3 | 6 — `test_a_curve_ends_where_its_tile_says.py` … |
| **release_cohort** | Écoutes d'un titre par jour depuis SA sortie (âge en jours). | `v_s4a_release_cohort` | `v_s4a_release_cohort.streams` | titre × âge | flux | depuis la sortie | 2 | 2 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **release_reach** | Portée d'une sortie : écoutes cumulées à J+7 / J+28. | `v_s4a_release_reach` | `v_s4a_release_reach` | titre | cumul | fenêtres fixes | 1 | 2 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **revenue_gross** | Revenus BRUTS au mois : distributeurs + SACEM (répartition). | `v_artist_monthly_revenue` | `v_artist_monthly_revenue.revenue_eur` | mois × source | flux | 12 mois | 14 | 6 — `test_a_failed_read_is_not_an_absence.py` … |
| **revenue_net** | Revenus NETS au mois, retenues déduites. | `v_artist_monthly_revenue_net` | `v_artist_monthly_revenue_net.net_eur` | mois × source | flux | 12 mois | 1 | 2 — `test_a_deduction_is_subtracted_from_the_right_base.py` … |
| **sacem** | Relevé SACEM au mois par nature de ligne (répartition, charges, virements). | `v_sacem_monthly` | `v_sacem_monthly.amount` | mois × nature | flux | tout | 3 | 3 — `test_a_deduction_is_subtracted_from_the_right_base.py` … |
| **soundcloud_catalog** | Écoutes, likes, reposts du catalogue, avec la lisibilité par métrique. | `v_soundcloud_catalog_daily` | `v_soundcloud_catalog_daily.plays (+ lisible)` | jour | cumul | période choisie | 3 | 1 — `test_a_chart_is_bounded_by_the_period_it_announces.py` |
| **soundcloud_track** | Les mêmes compteurs par titre. | `v_soundcloud_track_daily` | `v_soundcloud_track_daily.playback_count` | jour × titre | cumul | période choisie | 6 | 1 — `test_a_chart_is_bounded_by_the_period_it_announces.py` |
| **soundcloud_track_latest** | Dernier relevé par titre SoundCloud. | `v_soundcloud_track_latest` | `v_soundcloud_track_latest` | titre | cumul | dernier relevé | 5 | 4 — `test_a_failed_read_is_not_an_absence.py` … |
| **spotify_audience** | Auditeurs, écoutes, sauvegardes, ajouts en playlist (artiste) et niveau d'abonnés. | `v_s4a_audience_daily` | `v_s4a_audience_daily.listeners/saves/playlist_adds (flux) · followers_level (niveau)` | jour | flux | période choisie | 6 | 2 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **spotify_audience_monthly** | La même audience agrégée au mois (abonnés : dernier niveau). | `v_s4a_audience_monthly` | `v_s4a_audience_monthly` | mois | flux | 12 mois | 1 | 2 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **spotify_followers** | Abonnés Spotify de l'artiste (niveau), CSV S4A ou API selon la source. | `v_spotify_followers_daily` | `v_spotify_followers_daily.followers` | jour | niveau | période choisie | 1 | 3 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **spotify_measured_span** | Premier et dernier jour mesurés par titre — borne toute fenêtre. | `v_s4a_song_measured_span` | `v_s4a_song_measured_span.first_measured/last_measured` | titre | attribut | tout | 3 | 2 — `test_a_gold_view_is_blind_to_another_tenants_rows.py` … |
| **spotify_popularity** | Indice de popularité Spotify (0-100) par titre. | `v_spotify_track_pi_daily` | `v_spotify_track_pi_daily.popularity` | jour × titre | niveau | période choisie | 7 | **0** |
| **streams_all_platforms** | Écoutes par plateforme sur une fenêtre — LA porte des totaux. | `v_platform_totals` | `v_platform_totals.total` | plateforme | flux | période choisie | 15 | 11 — `test_a_curve_ends_where_its_tile_says.py` … |
| **streams_spotify** | Écoutes Spotify par titre et par jour (export S4A, ligne Total exclue). | `v_s4a_song_daily` | `v_s4a_song_daily.streams` | jour × titre | flux | période choisie | 35 | 7 — `test_a_failed_read_is_not_an_absence.py` … |

Objets or lus par une surface et absents du registre : **0**

- ⚠️ **mrr** hors couche or — `src/utils/mrr.py::mrr_by_plan_sql` (mrr_by_plan_sql() — une jointure, pas encore une vue or) : à conformer.

## Les figures d'écran

Une ligne par **site de code**, pas par figure rendue : une figure dans une boucle est un site et N images.

**57 sur 76** portent une source établie ; **6** sont déclarées indéterminées et listées en tête ; 13 sont hors base par nature — la tranche a fini proprement sans lire la base — et 49 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `utils/ml_widgets.py:219` | `render_prerelease_rr_estimator` | plotly_chart | à l'écran | — | — | indéterminée | appelants-multiples · profondeur | — |
| ⚠️ `views/admin.py:358` | `_render_costs` | plotly_chart | à l'écran | — | — | indéterminée | profondeur | — |
| ⚠️ `views/db_health.py:220` | `_show_freshness_bar` | plotly_chart | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/meta_breakdowns.py:124` | `_render_performance` | plotly_chart | à l'écran | — | — | indéterminée | clé-à-l-exécution | — |
| ⚠️ `views/meta_breakdowns.py:138` | `_render_performance` | plotly_chart | un clic | — | — | indéterminée | clé-à-l-exécution | — |
| ⚠️ `views/trigger_algo/_common/_pi_gates.py:76` | `_show_pi_gate_section` | plotly_chart | à l'écran | — | — | indéterminée | profondeur · sans-appelant | — |
| `utils/ml_widgets.py:301` | `render_lever_sensitivity` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `utils/platform_chart.py:1090` | `render_platform_chart` | plotly_chart | à l'écran | `get()` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `measured_days()` | or | plusieurs amonts | appelants-multiples · clé-à-l-exécution · profondeur · sans-appelant | — |
| `utils/platform_chart.py:1200` | `_render_facets` | plotly_chart | à l'écran | `get()` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `measured_days()` | or | plusieurs amonts | appelants-multiples · clé-à-l-exécution · profondeur | — |
| `utils/s4a_entry_insight.py:279` | `render_prediction_vs_reality` | plotly_chart | à l'écran | `ml_song_predictions` · `s4a_song_algo_outcomes` | brut | plusieurs amonts | clé-à-l-exécution · identifiant-non-résolu · profondeur | — |
| `utils/s4a_entry_insight.py:338` | `render_playlist_history` | plotly_chart | à l'écran | `s4a_song_playlist_adds` | brut | plusieurs amonts | — | — |
| `views/alerts.py:440` | `_section_plan_evolution` | plotly_chart | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plan_history` · `subscription_plans` | brut | plusieurs amonts | profondeur | — |
| `views/etl_logs.py:231` | `_section_trend` | plotly_chart | à l'écran | `etl_run_log` | brut | plusieurs amonts | — | — |
| `views/hypeddit.py:337` | `_render_campaign_series` | plotly_chart | à l'écran | `v_hypeddit_daily` | or | plusieurs amonts | — | — |
| `views/imusician.py:451` | `show` | plotly_chart | à l'écran | `v_artist_monthly_cashflow` · `v_artist_monthly_revenue` · `meta_insights_performance_day` | mixte | plusieurs amonts | profondeur · sql-dynamique | ?`saas_artists` |
| `views/instagram.py:255` | `show` | plotly_chart | à l'écran | `v_instagram_media_monthly` | or | plusieurs amonts | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` |
| `views/instagram.py:304` | `show` | plotly_chart | à l'écran | `v_instagram_media_monthly` | or | plusieurs amonts | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` |
| `views/instagram.py:434` | `_render_community` | plotly_chart | à l'écran | `instagram_daily_stats` · `instagram_media` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/meta_ads_overview.py:177` | `_render_global_perf` | plotly_chart | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/meta_ads_overview.py:439` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`v_meta_adset_daily` · ?`v_meta_daily` · ?`v_meta_engagement_daily` |
| `views/meta_ads_overview.py:542` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` · `v_meta_daily` | or | plusieurs amonts | — | ?`v_meta_adset_daily` · ?`v_meta_engagement_daily` |
| `views/meta_ads_overview.py:658` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_adset_daily` | or | plusieurs amonts | clé-à-l-exécution | ?`v_meta_campaign_daily` · ?`v_meta_daily` · ?`v_meta_engagement_daily` |
| `views/meta_cpr_optimizer.py:502` | `_render_age_panel` | plotly_chart | à l'écran | `meta_insights_performance_age` | brut | plusieurs amonts | — | — |
| `views/meta_creatives.py:451` | `_render_ranking` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:496` | `_render_hooks` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/meta_creatives.py:775` | `_render_creative_timeline` | plotly_chart | à l'écran | `v_artist_monthly_revenue` · `v_meta_creative_daily` · `meta_insights_performance_day` | mixte | plusieurs amonts | — | — |
| `views/meta_creatives.py:810` | `_render_scatter` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:845` | `_render_efficiency` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:897` | `_render_funnel` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:974` | `_render_fatigue` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:1004` | `_render_activity` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:1008` | `_render_activity` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/meta_x_spotify.py:452` | `_render_chart` | plotly_chart | à l'écran | `meta_insights_performance_day` | brut | plusieurs amonts | profondeur | — |
| `views/meta_x_spotify.py:731` | `_render_listener_verdict` | plotly_chart | à l'écran | `v_s4a_audience_daily` | or | plusieurs amonts | — | ?`v_meta_daily` |
| `views/meta_x_spotify.py:1024` | `_render_funnel` | plotly_chart | à l'écran | `v_hypeddit_daily` · `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`v_s4a_song_daily` |
| `views/meta_x_spotify.py:1157` | `_render_countries` | plotly_chart | à l'écran | `imusician_sales_detail` · `meta_insights_performance_country` | brut | plusieurs amonts | — | — |
| `views/revenue_forecast.py:248` | `_tab_projection` | plotly_chart | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/revenue_forecast.py:441` | `_render_money_chart` | plotly_chart | à l'écran | `v_artist_monthly_cashflow` · `v_artist_monthly_revenue` · `meta_insights_performance_day` | mixte | plusieurs amonts | profondeur · sql-dynamique | — |
| `views/revenue_forecast.py:717` | `_render_trigger_value` | plotly_chart | à l'écran | `algo_lifecycle_benchmark` · `ml_song_predictions` | brut | plusieurs amonts | — | ?`v_s4a_song_daily` |
| `views/sacem.py:145` | `show` | plotly_chart | à l'écran | `v_artist_monthly_cashflow` · `v_artist_monthly_revenue` · `meta_insights_performance_day` | mixte | plusieurs amonts | profondeur · sql-dynamique | — |
| `views/soundcloud.py:269` | `show` | plotly_chart | à l'écran | `v_soundcloud_track_daily` · `v_soundcloud_track_latest` · `soundcloud_tracks_daily` | mixte | plusieurs amonts | — | ?`v_soundcloud_catalog_daily` |
| `views/soundcloud.py:292` | `show` | plotly_chart | à l'écran | `v_soundcloud_track_daily` | or | plusieurs amonts | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_catalog_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:524` | `_render_top_chart` | plotly_chart | à l'écran | `v_soundcloud_track_latest` · `soundcloud_tracks_daily` | mixte | plusieurs amonts | — | — |
| `views/spotify_s4a_combined.py:359` | `_render_momentum` | plotly_chart | à l'écran | `v_s4a_song_daily` · `v_s4a_song_measured_span` · `v_spotify_track_pi_daily` | or | plusieurs amonts | profondeur | — |
| `views/trigger_algo/_tab_algo_streams.py:88` | `_show_tab_algo_streams` | plotly_chart | à l'écran | `s4a_song_algo_outcomes` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_algos.py:159` | `_show_tab_algos` | plotly_chart | à l'écran | `ml_song_predictions` · `s4a_song_timeline` · `track_popularity_history` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_algos.py:249` | `_show_tab_algos` | plotly_chart | à l'écran | `s4a_song_timeline` · `track_popularity_history` | brut | plusieurs amonts | sans-appelant | ?`ml_song_predictions` |
| `views/trigger_algo/_tab_budget_roi.py:363` | `_render_fit` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_budget_roi.py:522` | `_render_breakeven` | plotly_chart | à l'écran | `v_artist_monthly_revenue` · `v_meta_daily` · `imusician_monthly_revenue` · `track_popularity_history` | mixte | plusieurs amonts | profondeur | — |
| `views/trigger_algo/_tab_catalogue.py:158` | `_show_tab_catalogue` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/trigger_algo/_tab_lifecycle.py:48` | `_show_tab_lifecycle` | plotly_chart | à l'écran | `tracks` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:100` | `_show_tab_model` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:180` | `_show_volume_scatter` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/youtube.py:185` | `show` | plotly_chart | à l'écran | `youtube_cumulative_views()` · `youtube_channel_history` · `youtube_video_stats` · `youtube_videos` | mixte | plusieurs amonts | — | — |
| `views/youtube.py:376` | `show` | plotly_chart | à l'écran | `youtube_video_stats` · `youtube_videos` | brut | plusieurs amonts | clé-à-l-exécution | ?`youtube_channel_history` |
| `utils/ml_widgets.py:163` | `render_classification_scorecard` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:628` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:646` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:669` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/apple_music.py:147` | `show` | plotly_chart | à l'écran | `apple_songs_performance` | brut | directe | — | ?`v_apple_song_cumulative` · ?`v_apple_song_daily` |
| `views/apple_music.py:316` | `_render_song_series` | plotly_chart | à l'écran | `v_apple_song_daily` | or | portée (1 saut) | — | — |
| `views/db_health.py:262` | `_show_heatmap` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/db_health.py:330` | `_show_batch_sizes` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:172` | `_render_engagement` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:183` | `_render_engagement` | plotly_chart | un clic | — | — | hors base | — | — |
| `views/revenue_forecast.py:118` | `_tab_mrr` | plotly_chart | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | directe | — | — |
| `views/revenue_forecast.py:330` | `_tab_ltv` | plotly_chart | à l'écran | — | — | hors base | — | ?`v_artist_monthly_revenue` |
| `views/soundcloud.py:448` | `_render_catalog_series` | plotly_chart | à l'écran | `v_soundcloud_catalog_daily` | or | directe | — | — |
| `views/spotify_s4a_combined.py:230` | `_render_releases` | plotly_chart | à l'écran | `v_s4a_release_cohort` | or | directe | — | ?`v_s4a_release_reach` |
| `views/spotify_s4a_combined.py:451` | `_render_secondary` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_tab_explainability.py:104` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/trigger_algo/_tab_explainability.py:135` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/trigger_algo/_tab_explainability.py:169` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/usage_analytics.py:56` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |
| `views/usage_analytics.py:69` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |
| `views/usage_analytics.py:83` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |

## Les tuiles

`st.metric` n'est que 17 des 207 tuiles du produit ; les 190 autres passent par une poignée de colonne (`c1.metric`). Un inventaire qui n'aurait compté que le receveur `st` décrirait 8 % du produit.

**74 sur 169** portent une source établie ; **10** sont déclarées indéterminées et listées en tête ; 85 sont hors base par nature — la tranche a fini proprement sans lire la base — et 45 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `views/airflow_kpi.py:466` | `_render_insertion_test` | airflow_kpi.metric_dags_with_data | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:467` | `_render_insertion_test` | airflow_kpi.metric_dags_no_data | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:483` | `_render_insertion_test` | airflow_kpi.metric_rows | autre onglet | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:484` | `_render_insertion_test` | airflow_kpi.metric_days | autre onglet | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/alerts.py:449` | `_section_plan_evolution` | col.metric | à l'écran | — | — | indéterminée | receveur-inconnu | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| ⚠️ `views/db_health.py:145` | `_show_health_table` | db_health.kpi_total_rows | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/db_health.py:146` | `_show_health_table` | db_health.kpi_stale | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/imusician.py:299` | `show` | imusician.kpi_total | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| ⚠️ `views/imusician.py:300` | `show` | imusician.kpi_avg | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| ⚠️ `views/imusician.py:301` | `show` | imusician.kpi_months | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| `views/account.py:96` | `_section_profile` | account.plan | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | profondeur | — |
| `views/admin.py:342` | `_render_costs` | admin.costs_metric_mrr | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/admin.py:343` | `_render_costs` | admin.costs_metric_margin | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/admin.py:427` | `_render_supervision` | admin.metric_mrr | un clic | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_users` |
| `views/admin.py:428` | `_render_supervision` | admin.metric_paying | un clic | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_users` |
| `views/admin.py:429` | `_render_supervision` | admin.metric_arpu | un clic | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_users` |
| `views/admin_activation.py:51` | `_render_activation` | admin.metric_activation | à l'écran | `saas_artists` | brut | plusieurs amonts | identifiant-non-résolu | — |
| `views/airflow_kpi.py:601` | `show` | airflow_kpi.metric_avg_invalid | à l'écran | `etl_run_log` | brut | plusieurs amonts | — | — |
| `views/billing.py:352` | `_show_admin_view` | billing.total_mrr | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/billing.py:353` | `_show_admin_view` | billing.paying_artists | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/billing.py:354` | `_show_admin_view` | ARPU | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/home_tiles.py:226` | `_box` | — | autre onglet | `v_artist_monthly_cashflow` · `v_hypeddit_daily` · `v_instagram_followers_daily` · `v_meta_active_budget` · `v_meta_campaign_daily` · `v_meta_daily` · `gold_apple_lifetime` · `apple_yearly_series()` · `combined_total()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` · `meta_campaigns` · `meta_insights_performance_age` · `meta_insights_performance_country` · `meta_insights_performance_placement` · `ml_song_predictions` · `track_platform_link` · `track_release_reference` | mixte | plusieurs amonts | appelants-multiples · profondeur | — |
| `views/home_tiles.py:364` | `_u_shazam` | home.tile_shazam | autre onglet | `v_artist_monthly_cashflow` · `v_hypeddit_daily` · `v_instagram_followers_daily` · `v_meta_active_budget` · `v_meta_campaign_daily` · `v_meta_daily` · `gold_apple_lifetime` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` · `meta_campaigns` · `meta_insights_performance_age` · `meta_insights_performance_country` · `meta_insights_performance_placement` · `ml_song_predictions` · `track_platform_link` · `track_release_reference` | mixte | plusieurs amonts | — | — |
| `views/home_tiles.py:375` | `_u_instagram` | 📸 Instagram | autre onglet | `v_artist_monthly_cashflow` · `v_hypeddit_daily` · `v_instagram_followers_daily` · `v_meta_active_budget` · `v_meta_campaign_daily` · `v_meta_daily` · `gold_apple_lifetime` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` · `meta_campaigns` · `meta_insights_performance_age` · `meta_insights_performance_country` · `meta_insights_performance_placement` · `ml_song_predictions` · `track_platform_link` · `track_release_reference` | mixte | plusieurs amonts | — | — |
| `views/home_tiles.py:385` | `_u_meta` | home.tile_meta | autre onglet | `v_artist_monthly_cashflow` · `v_hypeddit_daily` · `v_instagram_followers_daily` · `v_meta_active_budget` · `v_meta_campaign_daily` · `v_meta_daily` · `gold_apple_lifetime` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` · `meta_campaigns` · `meta_insights_performance_age` · `meta_insights_performance_country` · `meta_insights_performance_placement` · `ml_song_predictions` · `track_platform_link` · `track_release_reference` | mixte | plusieurs amonts | — | — |
| `views/home_tiles.py:402` | `_u_hypeddit` | home.tile_hypeddit | autre onglet | `v_artist_monthly_cashflow` · `v_hypeddit_daily` · `v_instagram_followers_daily` · `v_meta_active_budget` · `v_meta_campaign_daily` · `v_meta_daily` · `gold_apple_lifetime` · `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` · `meta_campaigns` · `meta_insights_performance_age` · `meta_insights_performance_country` · `meta_insights_performance_placement` · `ml_song_predictions` · `track_platform_link` · `track_release_reference` | mixte | plusieurs amonts | — | — |
| `views/home_tiles.py:473` | `render_tiles` | — | autre onglet | `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `platform_totals()` | or | plusieurs amonts | profondeur | — |
| `views/meta_ads_overview.py:358` | `_show_meta_ads` | 💾 Saves | à l'écran | `v_meta_campaign_daily` · `v_meta_engagement_daily` | or | plusieurs amonts | — | ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:359` | `_show_meta_ads` | 🔄 Shares | à l'écran | `v_meta_campaign_daily` · `v_meta_engagement_daily` | or | plusieurs amonts | — | ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:360` | `_show_meta_ads` | meta_ads_overview.total_interactions | à l'écran | `v_meta_campaign_daily` · `v_meta_engagement_daily` | or | plusieurs amonts | — | ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_cpr_optimizer.py:279` | `_render_detail_cards` | meta_cpr_optimizer.composite_score | un clic | `v_meta_campaign_daily` · `campaign_track_mapping` · `ml_song_predictions` | mixte | plusieurs amonts | profondeur | — |
| `views/meta_cpr_optimizer.py:280` | `_render_detail_cards` | meta_cpr_optimizer.col_current_cpr | un clic | `v_meta_campaign_daily` · `campaign_track_mapping` · `ml_song_predictions` | mixte | plusieurs amonts | profondeur | — |
| `views/meta_cpr_optimizer.py:281` | `_render_detail_cards` | meta_cpr_optimizer.col_budget | un clic | `v_meta_campaign_daily` · `campaign_track_mapping` · `ml_song_predictions` | mixte | plusieurs amonts | profondeur | — |
| `views/meta_mapping/_tracks.py:297` | `_render_coverage_grid` | — | à l'écran | `track_platform_link` | brut | plusieurs amonts | — | — |
| `views/meta_x_spotify.py:311` | `_render_tiles` | meta_x_spotify.tile_spend | à l'écran | `meta_insights_performance_day` | brut | plusieurs amonts | profondeur | ?`v_instagram_followers_daily` |
| `views/meta_x_spotify.py:313` | `_render_tiles` | meta_x_spotify.tile_streams | à l'écran | `meta_insights_performance_day` | brut | plusieurs amonts | profondeur | ?`v_instagram_followers_daily` |
| `views/meta_x_spotify.py:317` | `_render_tiles` | meta_x_spotify.tile_cost_per_stream | à l'écran | `meta_insights_performance_day` | brut | plusieurs amonts | profondeur | ?`v_instagram_followers_daily` |
| `views/meta_x_spotify.py:326` | `_render_tiles` | meta_x_spotify.tile_conversion | à l'écran | `meta_insights_performance_day` | brut | plusieurs amonts | profondeur | ?`v_instagram_followers_daily` |
| `views/revenue_forecast.py:223` | `_tab_projection` | revenue_forecast.mrr_final | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/revenue_forecast.py:224` | `_tab_projection` | revenue_forecast.arr_final | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/revenue_forecast.py:226` | `_tab_projection` | revenue_forecast.months_to_target | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/revenue_forecast.py:312` | `_tab_ltv` | revenue_forecast.ltv_global | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:867` | `_tab_artist_forecast` | revenue_forecast.kpi_rythme | à l'écran | `v_artist_monthly_cashflow` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:873` | `_tab_artist_forecast` | revenue_forecast.kpi_breakeven | à l'écran | `v_artist_monthly_cashflow` | or | plusieurs amonts | clé-à-l-exécution · profondeur | ?`ml_song_predictions` |
| `views/trigger_algo/_common/_lifecycle.py:100` | `_standardization_block` | — | à l'écran | `v_s4a_song_daily` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_budget_roi.py:279` | `_show_tab_budget_roi` | trigger_algo.roi.remaining_budget_metric | un clic | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:365` | `_render_fit` | R² | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_budget_roi.py:367` | `_render_fit` | trigger_algo.roi.slope_metric | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_budget_roi.py:369` | `_render_fit` | p-value | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_catalogue.py:130` | `_show_tab_catalogue` | trigger_algo.cat.tile_closest | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/trigger_algo/_tab_catalogue.py:135` | `_show_tab_catalogue` | trigger_algo.cat.tile_progress | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/trigger_algo/_tab_lifecycle.py:37` | `_show_tab_lifecycle` | trigger_algo.lifecycle.age_metric | à l'écran | `tracks` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_titre.py:89` | `_show_tab_titre` | trigger_algo.titre.tile_gate | à l'écran | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `views/trigger_algo/_tab_titre.py:91` | `_show_tab_titre` | trigger_algo.titre.tile_value | à l'écran | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | profondeur | — |
| `views/trigger_algo/_tab_titre.py:95` | `_show_tab_titre` | trigger_algo.titre.tile_expect | à l'écran | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | clé-à-l-exécution · profondeur | — |
| `utils/ml_widgets.py:127` | `render_classification_scorecard` | AUC | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:133` | `render_classification_scorecard` | ml_widgets.precision | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:134` | `render_classification_scorecard` | Recall | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:135` | `render_classification_scorecard` | F1 | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:136` | `render_classification_scorecard` | Lift top-10% | à l'écran | — | — | hors base | — | — |
| `utils/platform_chart_notes.py:131` | `_render_recap` | — | autre onglet | — | — | hors base | — | — |
| `views/account.py:95` | `_section_profile` | account.username | à l'écran | — | — | hors base | — | — |
| `views/account.py:98` | `_section_profile` | account.email_verified | à l'écran | — | — | hors base | — | — |
| `views/account.py:102` | `_section_profile` | account.twofa | à l'écran | — | — | hors base | — | — |
| `views/admin.py:341` | `_render_costs` | admin.costs_metric_month | à l'écran | — | — | hors base | — | — |
| `views/admin.py:411` | `_render_supervision` | admin.metric_signups_7d | un clic | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:412` | `_render_supervision` | admin.metric_signups_30d | un clic | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:413` | `_render_supervision` | admin.metric_verified | un clic | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:414` | `_render_supervision` | admin.metric_active_artists | un clic | `saas_artists` | brut | directe | — | ?`artist_subscriptions` · ?`saas_users` · ?`subscription_plans` |
| `views/admin_accounts.py:409` | `_tab_users` | admin.metric_optin | à l'écran | — | — | hors base | — | ?`saas_artists` · ?`saas_users` |
| `views/airflow_kpi.py:205` | `_section_run_logs` | airflow_kpi.metric_total_lines | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:206` | `_section_run_logs` | airflow_kpi.metric_errors | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:207` | `_section_run_logs` | airflow_kpi.metric_warnings | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:303` | `_section_last_runs` | airflow_kpi.metric_total_dags | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:304` | `_section_last_runs` | airflow_kpi.metric_success | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:305` | `_section_last_runs` | airflow_kpi.metric_failures | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:306` | `_section_last_runs` | airflow_kpi.metric_never_run | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:473` | `_render_insertion_test` | airflow_kpi.metric_window | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:599` | `show` | airflow_kpi.metric_runs_24h | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:600` | `show` | airflow_kpi.metric_global_success | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:602` | `show` | airflow_kpi.metric_failures_7d | à l'écran | — | — | hors base | — | — |
| `views/alerts.py:446` | `_section_plan_evolution` | alerts.total_artists | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| `views/alerts.py:582` | `_section_trial_cohorts` | alerts.trial_granted | un clic | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| `views/alerts.py:583` | `_section_trial_cohorts` | alerts.trial_matured | un clic | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| `views/alerts.py:584` | `_section_trial_cohorts` | alerts.trial_paid | un clic | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| `views/alerts.py:594` | `_section_trial_cohorts` | alerts.trial_rate | un clic | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plan_history` · ?`subscription_plans` |
| `views/apple_music.py:100` | `show` | apple_music.kpi_streams | à l'écran | `apple_lifetime_plays()` | or | directe | — | ?`apple_songs_performance` · ?`v_apple_song_cumulative` · ?`v_apple_song_daily` |
| `views/apple_music.py:102` | `show` | apple_music.kpi_shazams | à l'écran | `apple_lifetime_shazams()` | or | directe | — | ?`apple_songs_performance` · ?`v_apple_song_cumulative` · ?`v_apple_song_daily` |
| `views/billing.py:173` | `_show_current_plan` | billing.metric_plan | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | directe | — | ?`saas_artists` |
| `views/billing.py:174` | `_show_current_plan` | billing.metric_price | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/billing.py:175` | `_show_current_plan` | billing.metric_status | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | directe | — | ?`saas_artists` |
| `views/data_wrapped.py:238` | `_tab_charts` | data_wrapped.field_listeners | à l'écran | `artist_wrapped` · `saas_artists` | brut | directe | — | — |
| `views/data_wrapped.py:241` | `_tab_charts` | data_wrapped.col_streams | à l'écran | `artist_wrapped` · `saas_artists` | brut | directe | — | — |
| `views/data_wrapped.py:244` | `_tab_charts` | data_wrapped.field_saves | à l'écran | `artist_wrapped` · `saas_artists` | brut | directe | — | — |
| `views/data_wrapped.py:247` | `_tab_charts` | data_wrapped.kpi_countries | à l'écran | `artist_wrapped` · `saas_artists` | brut | directe | — | — |
| `views/db_health.py:143` | `_show_health_table` | db_health.kpi_active | à l'écran | — | — | hors base | — | — |
| `views/db_health.py:144` | `_show_health_table` | db_health.kpi_empty | à l'écran | — | — | hors base | — | — |
| `views/etl_logs.py:78` | `_section_kpis` | etl_logs.kpi_runs | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:79` | `_section_kpis` | etl_logs.kpi_success_rate | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:82` | `_section_kpis` | etl_logs.kpi_avg_duration | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:83` | `_section_kpis` | etl_logs.kpi_rows_inserted | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/etl_logs.py:84` | `_section_kpis` | etl_logs.kpi_failed_runs | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/imusician.py:409` | `show` | imusician.roi_revenue | à l'écran | `fmt_eur()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:411` | `show` | imusician.roi_spend | à l'écran | `fmt_eur()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:423` | `show` | 📊 ROI | à l'écran | `get_roi_data()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:433` | `show` | 📊 ROI | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/imusician.py:438` | `show` | 📊 ROI | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/instagram.py:93` | `show` | instagram.kpi_followers | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:94` | `show` | instagram.kpi_follows | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:95` | `show` | instagram.kpi_media | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/meta_breakdowns.py:103` | `_render_performance` | meta_breakdowns.total_spend | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:105` | `_render_performance` | meta_breakdowns.results | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:107` | `_render_performance` | meta_breakdowns.avg_cpr | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:228` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_analyzed | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:229` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_no_cpr | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:231` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_increase | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:232` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_reduce | à l'écran | — | — | hors base | — | — |
| `views/meta_creatives.py:346` | `_render_decision_banner` | — | à l'écran | — | — | hors base | — | — |
| `views/meta_creatives.py:361` | `_render_decision_banner` | — | à l'écran | — | — | hors base | — | — |
| `views/meta_creatives.py:377` | `_render_decision_banner` | — | à l'écran | — | — | hors base | — | — |
| `views/referral.py:113` | `show` | referral.artists_referred | à l'écran | `referral_codes` | brut | directe | — | ?`referral_events` · ?`saas_artists` |
| `views/referral.py:114` | `show` | referral.free_months_earned | à l'écran | `saas_artists` | brut | directe | — | ?`referral_codes` · ?`referral_events` |
| `views/referral_admin.py:96` | `_render_creances` | referral_admin.owed_months | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:166` | `show` | referral_admin.metric_total_referrals | à l'écran | `referral_events` | brut | directe | — | ?`artist_subscriptions` · ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:167` | `show` | referral_admin.metric_converted | à l'écran | `artist_subscriptions` · `referral_events` | brut | directe | — | ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:168` | `show` | referral_admin.metric_conversion_rate | à l'écran | `artist_subscriptions` · `referral_events` | brut | directe | — | ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:169` | `show` | referral_admin.metric_free_months | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`referral_codes` · ?`referral_events` · ?`saas_artists` · ?`subscription_plans` |
| `views/revenue_forecast.py:93` | `_tab_mrr` | revenue_forecast.mrr_total | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:94` | `_tab_mrr` | ARPU | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:95` | `_tab_mrr` | revenue_forecast.paying_artists | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:96` | `_tab_mrr` | revenue_forecast.pending_cancellations | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:228` | `_tab_projection` | revenue_forecast.months_to_target | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:310` | `_tab_ltv` | ARPU | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | directe | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:311` | `_tab_ltv` | revenue_forecast.churn_monthly_metric | à l'écran | — | — | hors base | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:354` | `_tab_ltv` | revenue_forecast.avg_music_revenue | à l'écran | `v_artist_monthly_revenue` | or | directe | — | — |
| `views/revenue_forecast.py:355` | `_tab_ltv` | — | à l'écran | `v_artist_monthly_revenue` | or | directe | — | — |
| `views/revenue_forecast.py:860` | `_tab_artist_forecast` | revenue_forecast.kpi_cumul | à l'écran | — | — | hors base | — | ?`ml_song_predictions` · ?`v_artist_monthly_cashflow` |
| `views/revenue_forecast.py:910` | `_tab_artist_forecast` | 💿 iMusician | à l'écran | — | — | hors base | — | ?`ml_song_predictions` · ?`v_artist_monthly_cashflow` |
| `views/revenue_forecast.py:911` | `_tab_artist_forecast` | 🟢 DistroKid | à l'écran | — | — | hors base | — | ?`ml_song_predictions` · ?`v_artist_monthly_cashflow` |
| `views/revenue_forecast.py:912` | `_tab_artist_forecast` | 🎼 SACEM | à l'écran | — | — | hors base | — | ?`ml_song_predictions` · ?`v_artist_monthly_cashflow` |
| `views/sacem.py:104` | `show` | sacem.kpi_gross | à l'écran | `v_sacem_monthly` | or | directe | — | — |
| `views/sacem.py:105` | `show` | sacem.kpi_charges | à l'écran | `v_sacem_monthly` | or | directe | — | — |
| `views/sacem.py:106` | `show` | sacem.kpi_net | à l'écran | — | — | hors base | — | — |
| `views/soundcloud.py:137` | `show` | soundcloud.kpi_plays | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_catalog_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:138` | `show` | soundcloud.kpi_likes | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_catalog_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:139` | `show` | soundcloud.kpi_reposts | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_catalog_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:148` | `show` | soundcloud.kpi_comments | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_catalog_daily` · ?`v_soundcloud_track_latest` |
| `views/trigger_algo/_common/_budget_roi.py:146` | `_show_budget_pacing_calculator` | trigger_algo.common.pacing_daily_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` |
| `views/trigger_algo/_common/_pi_gates.py:45` | `_show_pi_gate_section` | trigger_algo.common.pi_predicted_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_tab_algo_streams.py:65` | `_show_tab_algo_streams` | 🟢 Discover Weekly | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:66` | `_show_tab_algo_streams` | 🩷 Release Radar | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:67` | `_show_tab_algo_streams` | 🟠 Radio | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:68` | `_show_tab_algo_streams` | trigger_algo.algostreams_total | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_budget_roi.py:82` | `_render_expected_value` | — | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_tab_budget_roi.py:170` | `_show_tab_budget_roi` | trigger_algo.roi.lifetime_budget_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:172` | `_show_tab_budget_roi` | trigger_algo.roi.spent_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:174` | `_show_tab_budget_roi` | trigger_algo.roi.remaining_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:179` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_stream_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:200` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_stream_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:280` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_submission_met | un clic | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:281` | `_show_tab_budget_roi` | trigger_algo.roi.possible_submissions_me | un clic | — | — | hors base | — | ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_catalogue.py:123` | `_show_tab_catalogue` | trigger_algo.cat.tile_active | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/usage_analytics.py:41` | `show` | usage_analytics.kpi_events | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/usage_analytics.py:42` | `show` | usage_analytics.kpi_sessions | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/usage_analytics.py:43` | `show` | usage_analytics.kpi_active_artists | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/useful_links.py:123` | `show` | Airflow UI | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:129` | `show` | Streamlit Dashboard | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:138` | `show` | REST API (FastAPI) | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:143` | `show` | API ReDoc | à l'écran | — | — | hors base | — | — |

## Les figures du PDF

Prises à leur site de câblage dans `_report.py` : les fonctions de `pdf_charts.py` reçoivent tout en paramètre, y trancher ne dirait rien.

**22 sur 29** portent une source établie ; **7** sont déclarées indéterminées et listées en tête ; 0 sont hors base par nature — la tranche a fini proprement sans lire la base — et 13 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `utils/pdf_exporter/_report.py:141` | `collect_report_data` | pdf_charts.streams_timeline | PDF | — | — | indéterminée | sans-appelant | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:156` | `collect_report_data` | pdf_charts.soundcloud_top_bar | PDF | — | — | indéterminée | sans-appelant | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:165` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sans-appelant · sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:168` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sans-appelant · sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:171` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sans-appelant · sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:184` | `collect_report_data` | pdf_charts.meta_funnel | PDF | — | — | indéterminée | sans-appelant | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:189` | `collect_report_data` | pdf_charts.ig_engagement | PDF | — | — | indéterminée | sans-appelant | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:147` | `collect_report_data` | pdf_charts.platform_evolution | PDF | `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:149` | `collect_report_data` | pdf_charts.j28_trajectory | PDF | `v_s4a_song_daily` · `tracks` | mixte | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:151` | `collect_report_data` | pdf_charts.treasury | PDF | `v_artist_monthly_cashflow` | or | plusieurs amonts | sql-dynamique | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:152` | `collect_report_data` | pdf_charts.top_songs_bar | PDF | `v_s4a_song_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:155` | `collect_report_data` | pdf_charts.youtube_top_videos_bar | PDF | `v_platform_totals` · `youtube_channel_history` · `youtube_video_stats` · `youtube_videos` | mixte | plusieurs amonts | profondeur | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:157` | `collect_report_data` | pdf_charts.top_songs_bar | PDF | `apple_songs_performance` | brut | plusieurs amonts | profondeur | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:164` | `collect_report_data` | pdf_charts.hypeddit_combo | PDF | `v_hypeddit_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:174` | `collect_report_data` | pdf_charts.revenue_forecast_chart | PDF | `v_artist_monthly_revenue` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:175` | `collect_report_data` | pdf_charts.indexed_lines | PDF | `v_meta_daily` · `v_s4a_song_daily` · `v_spotify_track_pi_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:186` | `collect_report_data` | pdf_charts.pi_gate | PDF | `tracks` | brut | plusieurs amonts | sans-appelant | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:187` | `collect_report_data` | pdf_charts.apple_timeline | PDF | `v_apple_song_cumulative` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:188` | `collect_report_data` | pdf_charts.sc_multiaxis | PDF | `soundcloud_tracks_daily` | brut | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:192` | `collect_report_data` | pdf_charts.youtube_channel_growth | PDF | `youtube_cumulative_views()` · `youtube_channel_history` | mixte | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:142` | `collect_report_data` | pdf_charts.platform_breakdown | PDF | `platform_totals()` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:148` | `collect_report_data` | pdf_charts.ml_probabilities | PDF | `tracks` | brut | portée (1 saut) | sans-appelant | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:161` | `collect_report_data` | pdf_charts.instagram_followers_line | PDF | `instagram_daily_stats` | brut | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:163` | `collect_report_data` | pdf_charts.meta_campaigns_bar | PDF | `v_meta_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:183` | `collect_report_data` | pdf_charts.playlist_adds_bars | PDF | `s4a_song_playlist_adds` | brut | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:185` | `collect_report_data` | pdf_charts.meta_daily | PDF | `v_meta_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:190` | `collect_report_data` | pdf_charts.s4a_cumulative | PDF | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:191` | `collect_report_data` | pdf_charts.s4a_audience_evolution | PDF | `v_s4a_audience_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:193` | `collect_report_data` | pdf_charts.song_timeline | PDF | `v_s4a_song_daily` | or | portée (1 saut) | sans-appelant | ?`s4a_song_timeline` |

## Les plateformes

Une ligne par plateforme. « Lectures brutes » compte les lectures de ses tables de fait **hors des portes** : ce n'est pas un compte de défauts — un catalogue de titres ou une date de dernier relevé n'a rien à centraliser — mais c'est là que la prochaine divergence naîtra.

| plateforme | tables de fait | vues or qui la définissent | lectures des vues or | lectures brutes |
|---|---|---|---|---|
| Apple Music | `apple_songs_history` · `apple_songs_performance` | `v_apple_song_cumulative` · `v_apple_song_daily` · `v_platform_totals` | 20 | 2 |
| Hypeddit | `hypeddit_daily_stats` | `v_hypeddit_daily` | 7 | 0 |
| Instagram | `instagram_daily_stats` · `instagram_media` | `v_instagram_followers_daily` · `v_instagram_media_monthly` | 5 | 11 |
| Meta Ads | `meta_ads` · `meta_adsets` · `meta_campaigns` · `meta_insights` · `meta_insights_performance` · `meta_insights_performance_day` | `v_artist_monthly_cashflow` · `v_meta_active_budget` · `v_meta_ad_daily` · `v_meta_adset_daily` · `v_meta_campaign_daily` · `v_meta_creative_daily` · `v_meta_daily` · `v_meta_spend_totals` · `v_meta_track_attribution` | 44 | 22 |
| Revenu | `distrokid_monthly_revenue` · `imusician_monthly_revenue` · `sacem_statement` | `v_artist_monthly_cashflow` · `v_artist_monthly_revenue` · `v_artist_monthly_revenue_net` · `v_sacem_monthly` | 15 | 4 |
| SoundCloud | `soundcloud_tracks_daily` | `v_platform_levels` · `v_platform_totals` · `v_soundcloud_catalog_daily` · `v_soundcloud_track_daily` · `v_soundcloud_track_latest` | 26 | 4 |
| Spotify S4A | `s4a_audience` · `s4a_song_timeline` · `s4a_songs_global` | `v_platform_levels` · `v_platform_totals` · `v_s4a_audience_daily` · `v_s4a_audience_monthly` · `v_s4a_release_cohort` · `v_s4a_release_reach` · `v_s4a_song_daily` · `v_s4a_song_measured_span` · `v_spotify_followers_daily` | 54 | 21 |
| YouTube | `youtube_channel_history` · `youtube_video_stats` | `v_platform_levels` · `v_platform_totals` | 17 | 8 |

## Les cliquets

**25 valeurs gelées** dans 19 fichiers. Un cliquet pose deux questions, et la seconde est celle qu'on oublie : le plafond est-il **serré** (égal à la mesure — un plafond au-dessus est du mou qui autorise en silence ce qu'il interdit), et la population est-elle **plancherée** ? « Zéro indéterminée » sur zéro figure est vrai et ne dit rien.

**0 sans test de non-vacuité** et **0 sans trace de mutation** dans leur fichier. Une trace de mutation est une phrase qui dit que le garde a été VU rouge sur le défaut qu'il vise ; sans elle, rien ne distingue un garde d'un test qui ne peut pas échouer.

Les deux colonnes de trou sont détectées sur le TEXTE du fichier de test (une phrase de mutation, un nom de test de non-vacuité) : un faux négatif est possible, il se corrige en écrivant la phrase.

| fichier | constante | valeur gelée | non-vacuité | trace de mutation |
|---|---|---|---|---|
| `test_a_chart_is_bounded_by_the_period_it_announces.py` | `_MAX_UNBOUNDED_FIGURES` | 0 | — | — |
| `test_a_failed_read_is_not_an_absence.py` | `_CEILING` | 0 | — | — |
| `test_a_gold_rule_is_declarative.py` | `_CEILING` | 1 | — | — |
| `test_a_page_asks_the_same_question_once.py` | `_MAX_QUERIES` | 2 entrées | — | — |
| `test_a_platform_colour_has_one_definition.py` | `_PLAFOND` | 42 | — | — |
| `test_a_sql_identifier_comes_from_a_closed_set.py` | `_MAX_UNSOURCED` | 0 | — | — |
| `test_a_suppressed_forecast_is_never_drawn.py` | `_FLOOR_COLS` | 3 entrées | — | — |
| `test_a_view_opens_on_one_decision.py` | `_MAX_FIRST_SCREEN` | 5 | — | — |
| `test_a_view_opens_on_one_decision.py` | `_PLAFOND_PAR_VUE` | 0 entrées | — | — |
| `test_chart_budget.py` | `_BUDGET` | 7 entrées | — | — |
| `test_the_bronze_boundary_only_tightens.py` | `_CEILING` | 66 | — | — |
| `test_the_declared_schema_matches_the_database.py` | `_PLAFOND` | 33 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MAX_ORPHANS` | 0 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MIN_TOTAL` | 296 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MIN_FAMILIES` | 17 | — | — |
| `test_the_gold_coverage_only_improves.py` | `_CEILING` | 11 entrées | — | — |
| `test_the_gold_coverage_only_improves.py` | `_FLOOR` | 10 entrées | — | — |
| `test_the_metrics_layer_only_grows.py` | `_CEILING` | 8 entrées | — | — |
| `test_the_resume_header_is_checked.py` | `_MAX_ACTIVE_LINES` | 250 | — | — |
| `test_the_shards_are_balanced_by_real_durations.py` | `_MAX_FILES_WITHOUT_DURATION` | 0 | — | — |
| `test_the_tenant_guard_is_written_once.py` | `_MAX_OPEN_CODED` | 0 | — | — |
| `test_the_visual_rules_only_tighten.py` | `_MAX_SECONDARY_AXES` | 0 | — | — |
| `test_the_visual_rules_only_tighten.py` | `_MAX_LITERAL_KEYS` | 115 | — | — |
| `test_the_websocket_survives_the_proxy.py` | `_MAX_SAFE_INTERVAL_S` | 60 | — | — |
| `test_the_websocket_survives_the_proxy.py` | `_MIN_SANE_INTERVAL_S` | 5 | — | — |

## Les classes d'erreur

**427 classes** au catalogue. Le regroupement en familles vit dans `error-class-families.md` ; ici on ne pose qu'une question, celle qui se périme : **le garde que la classe nomme existe-t-il encore ?** Une classe `guarded` dont le garde a été supprimé se lit exactement comme une classe gardée.

**fixed** : 10· **guarded** : 396· **open** : 4· **reported** : 15· **resolved** : 2

**0 classe(s) nomment un fichier de garde qui n'existe plus** et **8** ne nomment aucun chemin (leur garde est une règle transverse, un hook, ou rien).

_Aucune classe ne nomme un garde disparu._


Sans chemin de garde : `db-connection-per-show` · `view-session-adoption` · `snapshot-fixture-hook-reflow` · `dag-trigger-without-tenant-scope` · `repo-copy-of-a-config-is-not-what-runs` · `mermaid-block-does-not-render` · `guard-anchored-on-shape-not-question` · `a-guard-that-sees-the-binding-not-the-application`.


## Ce qui n'est gardé par rien

La question du livrable qui restait sans réponse : **quelles erreurs pourrait-on encore faire ?** Une case vide est une plateforme pour laquelle aucun garde de cette famille ne lit une seule de ses relations — donc un test à écrire, et c'est la liste des tests CI à intégrer.

Seules les familles de forme PLATEFORME sont ici. Un document périmé ou un seuil écrit d'instinct n'appartiennent à aucune plateforme ; les compter ainsi fabriquerait cent faux trous, et un livrable qui crie cent fois est un livrable que personne ne lit.

Le chiffre d'une case est le nombre de fichiers de garde qui NOMMENT une relation de cette plateforme dans un littéral SQL — jamais dans un commentaire : ce dépôt a pris quatre gardes au vert sur leur propre commentaire.

| famille | Apple Music | Hypeddit | Instagram | Meta Ads | Revenu | SoundCloud | Spotify S4A | YouTube |
|---|---|---|---|---|---|---|---|---|
| [le-locataire](error-class-families.md#le-locataire) | 3 | 2 | 3 | 6 | 6 | 4 | 4 | 4 |
| [un-cumul-pris-pour-un-quotidien](error-class-families.md#un-cumul-pris-pour-un-quotidien) | 2 | 1 | 1 | 2 | 1 | 2 | 2 | 3 |
| [deux-surfaces-deux-nombres](error-class-families.md#deux-surfaces-deux-nombres) | 6 | 1 | 3 | 13 | 4 | 6 | 13 | 6 |
| [une-erreur-avalée-devient-une-absence](error-class-families.md#une-erreur-avalée-devient-une-absence) | 2 | 2 | 2 | 3 | 2 | 4 | 4 | 2 |
| [un-nombre-affirmé-qui-n-a-pas-été-mesuré](error-class-families.md#un-nombre-affirmé-qui-n-a-pas-été-mesuré) | 3 | 1 | 3 | 7 | 4 | 4 | 6 | 3 |

Pourquoi ces familles et pas les autres :

| famille | pourquoi elle se pose par plateforme |
|---|---|
| `le-locataire` | chaque plateforme a ses tables, et chacune peut oublier le locataire dans SA jointure. Migration 064 l'a payé sur YouTube, la 107 sur SoundCloud, la 108 sur Meta. |
| `un-cumul-pris-pour-un-quotidien` | la question « cette colonne est-elle un compteur ou une quantité du jour » a une réponse DIFFÉRENTE par plateforme, et se retrompe à chaque nouvelle. |
| `deux-surfaces-deux-nombres` | un total par plateforme, donc une divergence possible par plateforme. |
| `une-erreur-avalée-devient-une-absence` | chaque plateforme a son `except` autour de sa lecture, et chacun peut rendre zéro à la place d'une panne. |
| `un-nombre-affirmé-qui-n-a-pas-été-mesuré` | une collecte ratée écrit des zéros, et ce qu'un zéro VEUT DIRE dépend de la plateforme — c'est tout l'objet de `value_monitor`. |

**0 case(s) vide(s)** — la liste des tests à écrire :

_aucune._


## Les invariants

**31 paires** de définitions or que rien n'oblige à coïncider sauf la donnée elle-même. ADR-019 garantit qu'une métrique a une seule **définition** ; que deux définitions censées coïncider coïncident est une propriété des DONNÉES, vérifiée chaque nuit par `alert_monitor.check_gold_invariants` et à chaque exécution de la suite par `tests/test_the_gold_layer_agrees_with_itself.py`.

Le défaut qui a fait naître cette section : `meta_insights_performance` et `meta_insights_performance_day` répondent à la même question et divergeaient d'un **facteur deux** en production, pendant des semaines. Chaque côté était cohérent avec lui-même ; personne ne comparait.

**0 objet(s) or ne sont touchés par aucun invariant** : aucun. Un objet que rien ne confronte peut dériver en silence — c'est le premier à le faire.

| invariant | un côté | l'autre |
|---|---|---|
| `meta_spend_two_grains` | `v_meta_daily` | `v_meta_campaign_daily` |
| `meta_engagement_view_vs_day_table` | `v_meta_engagement_daily` | `meta_insights_engagement_day` |
| `meta_ad_settings_view_loses_and_adds_nothing` | `v_meta_ad_daily` | `meta_insights[annonce connue du locataire]` |
| `meta_spend_creative_vs_adset` | `v_meta_creative_daily` | `v_meta_adset_daily` |
| `meta_spend_totals_vs_daily` | `v_meta_spend_totals` | `v_meta_daily` |
| `spotify_total_vs_song_grain` | `v_platform_totals[spotify]` | `v_s4a_song_daily` |
| `soundcloud_total_vs_track_grain` | `v_platform_totals[soundcloud]` | `v_soundcloud_track_latest` |
| `sacem_revenue_vs_statement_grain` | `v_artist_monthly_revenue[sacem]` | `v_sacem_monthly[repartition]` |
| `revenue_net_gross_vs_revenue_view` | `v_artist_monthly_revenue_net[gross]` | `v_artist_monthly_revenue` |
| `meta_attribution_campaign_count_vs_campaign_grain` | `v_meta_track_attribution[campaigns]` | `v_meta_campaign_daily` |
| `s4a_audience_day_vs_month` | `v_s4a_audience_daily` | `v_s4a_audience_monthly` |
| `s4a_span_vs_song_grain` | `v_s4a_song_measured_span` | `v_s4a_song_daily` |
| `s4a_release_cohort_loses_nothing` | `v_s4a_release_cohort` | `span[titres liés] − pre_release` |
| `s4a_reach_vs_cohort_days` | `v_s4a_release_reach[days_measured]` | `v_s4a_release_cohort` |
| `spotify_followers_csv_branch` | `v_spotify_followers_daily[s4a_csv]` | `v_s4a_audience_daily` |
| `instagram_followers_level_vs_raw` | `v_instagram_followers_daily` | `instagram_daily_stats` |
| `apple_total_vs_function` | `v_platform_totals[apple]` | `gold_apple_lifetime()` |
| `levels_vs_total_youtube` | `v_platform_levels[youtube] au dernier jour` | `v_platform_totals[youtube]` |
| `levels_vs_total_soundcloud` | `v_platform_levels[soundcloud] au dernier jour` | `v_platform_totals[soundcloud]` |
| `hypeddit_view_loses_no_row` | `v_hypeddit_daily` | `hypeddit_daily_stats` |
| `meta_active_budget_matches_its_filter` | `v_meta_active_budget` | `meta_campaigns[status=ACTIVE]` |
| `instagram_view_loses_no_post_that_has_a_date` | `v_instagram_media_monthly` | `instagram_media[timestamp non nul]` |
| `pi_view_keeps_every_reading_of_a_linked_track` | `v_spotify_track_pi_daily` | `track_popularity_history[liens confirmés]` |
| `apple_cumulative_keeps_both_sources` | `v_apple_song_cumulative` | `apple_songs_performance union apple_songs_history` |
| `apple_gains_telescope_to_the_cumulative` | `v_apple_song_daily[somme des gains]` | `v_apple_song_cumulative[dernier moins premier]` |
| `soundcloud_catalog_equals_its_tracks` | `v_soundcloud_catalog_daily` | `v_soundcloud_track_daily` |
| `soundcloud_latest_is_the_last_readable_day` | `v_soundcloud_track_latest[total]` | `v_soundcloud_catalog_daily[dernier jour lisible]` |
| `cashflow_revenue_vs_net_source` | `v_artist_monthly_cashflow (revenus)` | `v_artist_monthly_revenue_net` |
| `cashflow_meta_spend_vs_gold` | `v_artist_monthly_cashflow (meta_ads)` | `v_meta_daily` |
| `spread_costs_vs_raw_entries` | `v_artist_monthly_costs (étalement)` | `artist_cost_entries (arithmétique des bornes)` |
| `fleet_cashflow_is_the_sum_of_humans` | `trésorerie admin « tous les artistes » (flotte)` | `somme des soldes des locataires humains` |

## Les étapes de la CI

**17 étapes**, dont **17 bloquantes**. Lu dans `.github/workflows/ci.yml`, jamais récité — une liste d'étapes écrite à la main décrit la CI qu'on croit avoir.

⚠️ Une CI rouge cache tout ce qui la suit : ce dépôt l'a mesuré deux fois (8 exécutions bloquées à l'étape 3/8, puis 27 à l'étape 10/15). C'est `if: !cancelled()` qui l'a arrêté, pas la leçon écrite entre les deux.

| # | étape | ce qu'elle lance | rôle |
|---|---|---|---|
| 1 | Install uv | — | bloquante |
| 2 | Set up Python 3.11 | — | bloquante |
| 3 | Install dependencies from lockfile | sync | bloquante |
| 4 | Manifest consistency (blocking) | check_manifest_consistency.py | bloquante |
| 5 | Lint (ruff) — full project (blocking) | ruff check | bloquante |
| 6 | Mint a throwaway Fernet key for the collection gates | — | bloquante |
| 7 | REX integrity + static error-class guards (blocking) | validate_rex.py, audit_runner.py, audit_unreachable_tools.py, check_config_refs.py, pytest, check_durations_ar | bloquante |
| 8 | Install uv | — | bloquante |
| 9 | Set up Python 3.11 | — | bloquante |
| 10 | Install dependencies from lockfile | sync | bloquante |
| 11 | Provision Postgres (schema + migrations) | — | bloquante |
| 12 | Mint a throwaway Fernet key for this run | — | bloquante |
| 13 | Run tests | — | bloquante |
| 14 | Install pinned gitleaks | install_gitleaks.sh | bloquante |
| 15 | Scan the commits of this push / PR (blocking) | — | bloquante |
| 16 | Every product-code commit cites an open roadmap row (blocking) | require_roadmap_id.py | bloquante |
| 17 | Mail the owner when main turns red | ci_break_mail.py | bloquante |

## Ce qui n'est atteint par rien

C'est la vraie valeur de ce document. Les deux tableaux ne disent pas la même chose et il ne faut pas les lire pareil.

**Vues or que rien ne lit dans `src/` :** aucune. Une vue or sans lecteur est du travail gelé — soit la surface qui devait la lire ne l'a jamais fait, soit la vue n'avait pas lieu d'être.

Le second tableau liste les **tables brutes encore lues hors des portes**, alors qu'une vue or couvre le même grain. Ce n'est pas une liste de défauts : une lecture non agrégée — un catalogue, une date de dernier relevé, une liste de titres — n'a pas de définition à centraliser.

**La colonne qui compte est « dont hors cliquet ».** `tests/test_the_metrics_layer_only_grows.py` tient les agrégats à zéro, mais seulement sur les répertoires qu'il nomme `src/dashboard/views` · `src/dashboard/utils` · `src/api/routers` et sur les tables de sa propre liste de faits. Un agrégat hors de ces deux périmètres n'est gardé par rien. C'est exactement la forme du défaut du 2026-09-12 : le cliquet disait zéro, douze agrégats vivaient dans un répertoire qu'il ne nommait pas. Ces lignes-là sont les suivantes à regarder — chacune est soit un agrégat à repointer, soit un `MIN`/`MAX`/`COUNT` d'inventaire qui n'a rien à centraliser.

| table brute | vue or qui la couvre | lectures | agrégeantes | dont hors cliquet | où (les hors-cliquet d'abord) |
|---|---|---|---|---|---|
| `apple_songs_performance` | `v_apple_song_daily` | 2 | — | 0 | dashboard/utils/pdf_exporter/_collectors.py:461 · dashboard/views/apple_music.py:122 |
| `artist_cost_entries` | `v_artist_monthly_costs` | 1 | — | 0 | dashboard/views/revenue_forecast.py:575 |
| `distrokid_monthly_revenue` | `v_artist_monthly_revenue_net` | 1 | 1 | 0 | utils/distrokid_rollup.py:59 |
| `imusician_monthly_revenue` | `v_artist_monthly_revenue_net` | 2 | 1 | 0 | utils/imusician_rollup.py:42 |
| `instagram_daily_stats` | `v_instagram_followers_daily` | 8 | 2 | 0 | dashboard/utils/pdf_exporter/_collectors.py:344 · dashboard/views/instagram.py:136 |
| `instagram_media` | `v_instagram_media_monthly` | 3 | 2 | 0 | dashboard/views/instagram.py:214 · dashboard/views/instagram.py:337 |
| `meta_ads` | `v_meta_ad_daily` | 5 | 3 | 0 | dashboard/views/meta_creatives.py:1085 · dashboard/views/meta_mapping/_campaigns.py:42 · dashboard/views/trigger_algo/_common/_budget_roi.py:221 |
| `meta_adsets` | `v_meta_adset_daily` | 3 | 1 | 0 | dashboard/views/meta_mapping/_campaigns.py:42 |
| `meta_campaigns` | `v_meta_ad_daily` | 11 | 8 | 0 | dashboard/utils/period_side_metrics.py:84 · dashboard/views/meta_creatives.py:1085 · dashboard/views/meta_mapping/_campaigns.py:141 · dashboard/views/meta_mapping/_campaigns.py:156 · dashboard/views/meta_mapping/_campaigns.py:25 · dashboard/views/meta_mapping/_campaigns.py:42 · dashboard/views/trigger_algo/_common/_budget_roi.py:221 · utils/freshness_monitor.py:317 |
| `meta_insights` | `v_meta_ad_daily` | 1 | 1 | 0 | dashboard/views/meta_creatives.py:1085 |
| `meta_insights_performance` | `v_meta_campaign_daily` | 1 | 1 | 0 | dashboard/views/meta_mapping/_campaigns.py:191 |
| `meta_insights_performance_day` | `v_meta_campaign_daily` | 6 | 5 | 0 | collectors/_meta_insight_fetch.py:66 · dashboard/views/imusician.py:33 · dashboard/views/imusician.py:42 · dashboard/views/meta_x_spotify.py:745 · dashboard/views/meta_x_spotify.py:765 |
| `s4a_song_timeline` | `v_s4a_song_daily` | 16 | 4 | 0 | api/routers/streams.py:92 · dashboard/utils/pdf_exporter/_report.py:79 · dashboard/utils/setup_completion.py:281 · utils/freshness_monitor.py:260 |
| `saas_artists` | `v_spotify_followers_daily` | 64 | 9 | 0 | dashboard/utils/live_pulse.py:118 · dashboard/utils/live_pulse.py:68 · dashboard/views/admin.py:409 · dashboard/views/meta_mapping/_campaigns.py:191 · dashboard/views/referral_admin.py:149 · dashboard/views/referral_admin.py:176 · utils/daily_ops_metrics.py:206 · utils/defect_gauge.py:108 |
| `sacem_statement` | `v_sacem_monthly` | 1 | — | 0 | dashboard/views/sacem.py:32 |
| `soundcloud_tracks_daily` | `v_soundcloud_track_daily` | 4 | 1 | 0 | dashboard/views/soundcloud.py:89 |
| `track_platform_link` | `v_spotify_track_pi_daily` | 8 | 2 | 0 | dashboard/utils/period_side_metrics.py:84 · dashboard/utils/setup_completion.py:281 |
| `track_popularity_history` | `v_spotify_track_pi_daily` | 6 | — | 0 | dashboard/views/trigger_algo/_tab_algos.py:175 · dashboard/views/trigger_algo/_tab_algos.py:184 · dashboard/views/trigger_algo/_tab_algos.py:79 · dashboard/views/trigger_algo/_tab_algos.py:95 · dashboard/views/trigger_algo/_tab_budget_roi.py:385 · dashboard/views/trigger_algo/_tab_budget_roi.py:406 |
| `track_release_reference` | `v_spotify_track_pi_daily` | 7 | 3 | 0 | dashboard/utils/period_filter.py:197 · dashboard/utils/period_side_metrics.py:84 · utils/freshness_monitor.py:260 |
| `youtube_video_stats` | `v_platform_levels` | 5 | 2 | 0 | dashboard/utils/pdf_exporter/_collectors.py:296 · dashboard/views/youtube.py:271 |

### Les tables de DIMENSION

**8 tables** ne portent aucune quantité additive : que des identifiants, des libellés, des dates ou un score par ligne. Une lecture de l'une d'elles ne peut pas être une règle métier recopiée — il n'y a rien à sommer — donc elle n'a jamais besoin d'être déclarée site par site.

Le critère se vérifie contre le schéma réel : `tests/test_a_dimension_table_carries_no_quantity.py` fait rougir la CI si l'une d'elles gagne une colonne additive. C'est une assertion, pas une liste de confiance. R108, tranché le 2026-09-14 — le registre a remplacé **7 déclarations de site** qui se multipliaient à chaque vue or neuve.

| table | pourquoi elle ne porte aucune quantité |
|---|---|
| `artist_subscriptions` | qui est abonné à quel plan. Ses trois entiers sont des identifiants — `id`, `artist_id`, `plan_id`. Le PRIX vit dans la table des plans, pas ici. |
| `campaign_track_mapping` | le rapprochement campagne ↔ titre, exactement la forme de `track_platform_link` : des identifiants et un `confidence` par ligne. |
| `hypeddit_campaigns` | le CATALOGUE des campagnes Hypeddit — un nom, un identifiant. Les visites et les clics vivent dans `hypeddit_daily_stats`, couverte par v_hypeddit_daily. |
| `saas_artists` | le REGISTRE des locataires. Ses seuls entiers sont un identifiant et deux paramètres de facturation par compte — rien à sommer entre deux lignes. |
| `track_platform_link` | la table de LIENS entre un titre et son identité sur une plateforme. `confidence` est un score par ligne, pas une quantité qui s'additionne. |
| `track_release_reference` | la table des SORTIES : une clé canonique, un titre, une date. Aucun nombre mesuré. |
| `tracks` | le CATALOGUE Spotify. `popularity` est un score par ligne ; `duration_ms` est une propriété INTRINSÈQUE d'un titre — sommer des durées répond à une question que ce produit ne pose jamais, et rien ne les somme aujourd'hui (vérifié : aucun SUM/AVG sur ces deux colonnes dans src/). Chaque lecture de cette table cherche un nom, un track_id ou une date de sortie. |
| `youtube_videos` | le CATALOGUE des vidéos — un titre, un identifiant, une date. Les vues et les likes vivent dans `youtube_video_stats`, qui n'est PAS une dimension. |

### Les agrégats DÉCLARÉS

**13 couples (fichier, table)** agrègent une table de fait hors de tout cliquet, délibérément. La frontière est nette : un COMPTE, une DATE ou une CONCATÉNATION de noms répond « qu'y a-t-il » ; une somme d'argent, d'écoutes, de vues ou de clics répond « combien » et appartient à la couche or, sans exception.

Chaque déclaration est vérifiée : le site doit encore exister et encore agréger cette table. Une déclaration qui survit à ce qu'elle déclarait est du budget pour la prochaine occurrence.

| fichier | table | pourquoi ce n'est pas une métrique |
|---|---|---|
| `collectors/_meta_insight_fetch.py` | `meta_insights_performance_day` | MAX(day_date) : le point de reprise de la collecte incrémentale. Un collecteur n'est pas une surface, et cette date n'est affichée nulle part. |
| `dashboard/utils/period_side_metrics.py` | `meta_campaigns` | `meta_campaigns_known` : COUNT(*) de TOUTES les campagnes connues d'un locataire, pour distinguer « aucune active » de « on ne sait rien de ses campagnes » (l'artiste 18). Un inventaire, sans règle métier : la règle `status = 'ACTIVE'` passe, elle, par `v_meta_active_budget` (2026-09-24). |
| `dashboard/views/meta_creatives.py` | `meta_ads` | même requête : le COUNT des créatives d'une campagne dont les insights manquent. Un décompte de diagnostic, jamais affiché comme une mesure. |
| `dashboard/views/meta_creatives.py` | `meta_campaigns` | `_QUERY_UNCOLLECTED` : COUNT(DISTINCT ad_id) et un `HAVING SUM(spend) = 0` qui SÉLECTIONNE les campagnes sans détail par créative. Le montant affiché à côté vient de `v_meta_daily` ; ici la somme est un prédicat, pas un nombre — et elle doit porter sur la table de fait, puisque la question est précisément « cette table est-elle vide pour cette campagne ». |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_ads` | string_agg des noms de créatives, pour reconnaître de quelle sortie parle une campagne. Un nom n'est pas une mesure. |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_adsets` | MIN/MAX des dates d'activité d'un ad set, pour comparer à la date de sortie du titre. Une fenêtre, pas un chiffre affiché. |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_campaigns` | catalogue de campagnes à associer : MAX(start_time), string_agg de noms, bool_or d'un marqueur de rejet. Aucun montant, aucune performance. |
| `dashboard/views/trigger_algo/_common/_budget_roi.py` | `meta_ads` | même requête que ci-dessus : la jointure vers les créatives sert à lire leur call_to_action, jamais à sommer. |
| `dashboard/views/trigger_algo/_common/_budget_roi.py` | `meta_campaigns` | string_agg(DISTINCT call_to_action) — l'inventaire des appels à l'action d'une campagne, à côté de sa performance qui, elle, vient de la couche or. |
| `utils/distrokid_rollup.py` | `distrokid_monthly_revenue` | COUNT(*) des mois issus d'un import, renvoyé par le rollup qui vient de les écrire. C'est un accusé de réception, pas un revenu. |
| `utils/freshness_monitor.py` | `meta_campaigns` | count(*) FILTER (status = 'ACTIVE') — une sonde de santé. Elle demande « ce locataire a-t-il des campagnes », pas « combien ont-elles coûté ». |
| `utils/freshness_monitor.py` | `s4a_song_timeline` | MAX(date) : jusqu'où la mesure va, pour décider si une sortie attend d'être importée. Une borne, jamais un volume — et rien de ce nombre n'est affiché. |
| `utils/imusician_rollup.py` | `imusician_monthly_revenue` | idem : le compte des mois que le rollup vient d'écrire. |

## Les chiffres gelés

Ces compteurs sont écrits par la machine. Le cliquet `tests/test_the_gold_coverage_only_improves.py` les compare à un plafond posé **à** la mesure, jamais au-dessus.

<!-- gold-coverage-figures: total=76 unknown=6 -->
<!-- gold-coverage-tiles: total=169 unknown=10 -->
<!-- gold-coverage-pdf: total=29 unknown=7 -->
<!-- gold-coverage-gold-objects: total=33 orphans=0 -->
<!-- gold-coverage-unguarded-aggregates: total=0 -->
<!-- gold-coverage-ratchets: total=25 without_nonvacuity=0 without_mutation=0 -->
<!-- gold-coverage-error-classes: total=427 guard_missing=0 guard_unnamed=8 -->
<!-- gold-coverage-guard-matrix: cells=40 holes=0 -->
<!-- gold-coverage-invariants: pairs=31 unreconciled=0 -->
<!-- gold-coverage-ci: steps=17 blocking=17 -->

<!-- gold-coverage: sha256=0e23e79e91d8b869284c3fec106e03eb2b14440b9e21083fc4a1d5017d982a59 -->
