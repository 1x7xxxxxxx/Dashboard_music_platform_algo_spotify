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
| `identifiant-non-résolu` | un nom capté dans un FROM qui n'existe ni en migration ni dans init_db.sql (CTE, alias, sous-requête) — écarté plutôt que publié | 0 |
| `appelants-multiples` | rendu partagé par plus de trois appelants : un site, N jeux de données | 17 |
| `profondeur` | chaîne de plus de 3 sauts — plafond MESURÉ : le cran suivant n'apporte rien | 12 |
| `sans-appelant` | fonction dont aucun appel n'est résoluble statiquement | 3 |
| `clé-à-l-exécution` | argument passé par **kwargs, partial, ou conteneur indexé par une variable | 5 |
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
| `gold_apple_lifetime` | fonction | `migrations/113_gold_apple_absence_is_not_zero.sql` | `apple_songs_performance` | 2 | `migrations/102_gold_apple.sql` · `migrations/103_gold_apple_metric.sql` |
| `v_artist_monthly_revenue` | vue | `init_db.sql` | `distrokid_monthly_revenue` · `imusician_monthly_revenue` · `sacem_statement` | 20 | `migrations/056_v_artist_monthly_revenue.sql` · `migrations/111_gold_sacem_monthly.sql` |
| `v_hypeddit_daily` | vue | `migrations/106_gold_remaining_grains.sql` | `hypeddit_daily_stats` | 5 | — |
| `v_instagram_media_monthly` | vue | `migrations/106_gold_remaining_grains.sql` | `instagram_media` | 4 | — |
| `v_meta_active_budget` | vue | `migrations/110_gold_meta_active_budget.sql` | `meta_campaigns` | 4 | — |
| `v_meta_adset_daily` | vue | `migrations/108_gold_meta_creative_account_and_adset.sql` | `meta_ads` · `meta_adsets` · `meta_insights` | 1 | — |
| `v_meta_campaign_daily` | vue | `migrations/109_gold_meta_campaign_daily.sql` | `meta_insights_performance` · `meta_insights_performance_day` | 26 | — |
| `v_meta_creative_daily` | vue | `migrations/108_gold_meta_creative_account_and_adset.sql` | `meta_ads` · `meta_adsets` · `meta_campaigns` · `meta_insights` | 17 | `migrations/106_gold_remaining_grains.sql` |
| `v_meta_daily` | vue | `migrations/106_gold_remaining_grains.sql` | `meta_insights_performance_day` | 20 | — |
| `v_meta_spend_totals` | vue | `migrations/101_gold_meta_spend.sql` | `meta_insights_performance_day` | 1 | — |
| `v_platform_levels` | vue | `migrations/112_gold_partial_collection_is_not_a_level.sql` | `s4a_song_timeline` · `soundcloud_tracks_daily` · `youtube_video_stats` | 3 | `migrations/104_gold_platform_levels.sql` |
| `v_platform_totals` | vue | `migrations/107_gold_soundcloud_track_latest.sql` | `apple_songs_performance` · `gold_apple_lifetime` · `v_s4a_song_daily` · `v_soundcloud_track_latest` · `youtube_video_stats` | 15 | `migrations/097_v_platform_totals.sql` · `migrations/102_gold_apple.sql` · `migrations/103_gold_apple_metric.sql` |
| `v_s4a_song_daily` | vue | `migrations/105_gold_s4a_song_daily.sql` | `s4a_song_timeline` | 44 | — |
| `v_sacem_monthly` | vue | `migrations/111_gold_sacem_monthly.sql` | `sacem_statement` | 4 | — |
| `v_soundcloud_track_latest` | vue | `migrations/107_gold_soundcloud_track_latest.sql` | `soundcloud_tracks_daily` | 3 | — |

## Les figures d'écran

Une ligne par **site de code**, pas par figure rendue : une figure dans une boucle est un site et N images.

**60 sur 89** portent une source établie ; **7** sont déclarées indéterminées et listées en tête ; 22 sont hors base par nature — la tranche a fini proprement sans lire la base — et 52 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `utils/ml_widgets.py:224` | `render_prerelease_rr_estimator` | plotly_chart | à l'écran | — | — | indéterminée | appelants-multiples · profondeur | — |
| ⚠️ `utils/ml_widgets.py:294` | `render_lever_sensitivity` | plotly_chart | à l'écran | — | — | indéterminée | clé-à-l-exécution · profondeur | — |
| ⚠️ `views/admin.py:466` | `_render_costs` | plotly_chart | à l'écran | — | — | indéterminée | appelants-multiples · profondeur | — |
| ⚠️ `views/db_health.py:234` | `_show_freshness_bar` | plotly_chart | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/meta_ads_overview.py:637` | `_show_meta_ads` | plotly_chart | à l'écran | — | — | indéterminée | clé-à-l-exécution | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_campaign_daily` · ?`v_meta_daily` |
| ⚠️ `views/meta_breakdowns.py:96` | `_render_performance` | plotly_chart | à l'écran | — | — | indéterminée | clé-à-l-exécution | — |
| ⚠️ `views/trigger_algo/_common/_pi_gates.py:76` | `_show_pi_gate_section` | plotly_chart | à l'écran | — | — | indéterminée | profondeur | — |
| `utils/platform_chart.py:999` | `render_platform_chart` | plotly_chart | à l'écran | `get()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `measured_days()` | or | plusieurs amonts | appelants-multiples · clé-à-l-exécution · profondeur | — |
| `utils/platform_chart.py:1092` | `_render_facets` | plotly_chart | à l'écran | `get()` · `cumulative_by_platform()` · `daily_streams_by_platform()` · `measured_days()` | or | plusieurs amonts | appelants-multiples · clé-à-l-exécution · profondeur | — |
| `views/alerts.py:277` | `_section_plan_evolution` | plotly_chart | à l'écran | `subscription_plan_history` | brut | plusieurs amonts | — | — |
| `views/apple_music.py:100` | `show` | plotly_chart | à l'écran | `apple_songs_history` · `apple_songs_performance` | brut | plusieurs amonts | — | — |
| `views/apple_music.py:212` | `show` | plotly_chart | à l'écran | `apple_songs_history` · `apple_songs_performance` | brut | plusieurs amonts | — | — |
| `views/data_wrapped.py:628` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:638` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:644` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:661` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:667` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:675` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:681` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/data_wrapped.py:695` | `show` | plotly_chart | à l'écran | `artist_wrapped` · `saas_artists` | brut | plusieurs amonts | appelants-multiples | — |
| `views/etl_logs.py:230` | `_section_trend` | plotly_chart | à l'écran | `etl_run_log` | brut | plusieurs amonts | — | — |
| `views/hypeddit.py:209` | `_render_global_stats` | plotly_chart | à l'écran | `v_hypeddit_daily` | or | plusieurs amonts | — | — |
| `views/imusician.py:329` | `show` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | sql-dynamique | ?`saas_artists` |
| `views/imusician.py:488` | `show` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | sql-dynamique | ?`saas_artists` |
| `views/instagram.py:86` | `show` | plotly_chart | à l'écran | `instagram_daily_stats` | brut | plusieurs amonts | appelants-multiples | ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:190` | `show` | plotly_chart | à l'écran | `v_instagram_media_monthly` | or | plusieurs amonts | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` |
| `views/instagram.py:221` | `show` | plotly_chart | à l'écran | `v_instagram_media_monthly` | or | plusieurs amonts | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` |
| `views/meta_ads_overview.py:216` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:330` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` · `meta_insights_engagement` | mixte | plusieurs amonts | — | ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:392` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` · `meta_insights_engagement` | mixte | plusieurs amonts | — | ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:469` | `_show_meta_ads` | plotly_chart | à l'écran | `v_meta_campaign_daily` · `v_meta_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` |
| `views/meta_creatives.py:243` | `_render_bar_chart` | bar_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:396` | `_render_creative_timeline` | plotly_chart | à l'écran | `v_artist_monthly_revenue` · `v_meta_creative_daily` · `meta_insights_performance_day` | mixte | plusieurs amonts | — | — |
| `views/meta_creatives.py:431` | `_render_scatter` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:453` | `_render_efficiency` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:524` | `_render_fatigue` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:554` | `_render_activity` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:566` | `_render_activity` | plotly_chart | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_x_spotify.py:305` | `_show_body` | plotly_chart | à l'écran | `hypeddit_daily_stats` · `meta_insights_performance_day` · `s4a_song_timeline` · `track_popularity_history` | brut | plusieurs amonts | — | ?`campaign_track_mapping` |
| `views/revenue_forecast.py:422` | `_tab_artist_forecast` | plotly_chart | à l'écran | `v_artist_monthly_revenue` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:497` | `_tab_artist_forecast` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:652` | `_tab_artist_forecast` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/sacem.py:96` | `show` | plotly_chart | à l'écran | `sacem_statement` | brut | plusieurs amonts | — | — |
| `views/soundcloud.py:155` | `show` | plotly_chart | à l'écran | `soundcloud_tracks_daily` | brut | plusieurs amonts | appelants-multiples · profondeur · sql-dynamique | ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:247` | `show` | plotly_chart | à l'écran | `soundcloud_tracks_daily` | brut | plusieurs amonts | appelants-multiples · profondeur · sql-dynamique | ?`v_soundcloud_track_latest` |
| `views/spotify_s4a_combined.py:225` | `show` | plotly_chart | à l'écran | `v_s4a_song_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/trigger_algo/_tab_algo_streams.py:78` | `_show_tab_algo_streams` | plotly_chart | à l'écran | `s4a_song_algo_outcomes` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_algos.py:138` | `_show_tab_algos` | plotly_chart | à l'écran | `ml_song_predictions` · `s4a_song_timeline` · `track_popularity_history` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_algos.py:228` | `_show_tab_algos` | plotly_chart | à l'écran | `s4a_song_timeline` · `track_popularity_history` · `tracks` | brut | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/trigger_algo/_tab_budget_roi.py:298` | `_show_tab_budget_roi` | plotly_chart | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:479` | `_show_tab_budget_roi` | plotly_chart | à l'écran | `v_artist_monthly_revenue` · `v_meta_daily` · `imusician_monthly_revenue` · `track_popularity_history` | mixte | plusieurs amonts | — | ?`v_meta_active_budget` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:162` | `_show_tab_global` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | ?`s4a_song_playlist_adds` · ?`s4a_song_timeline` · ?`s4a_songs_global` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_lifecycle.py:48` | `_show_tab_lifecycle` | plotly_chart | à l'écran | `tracks` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:90` | `_show_tab_model` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:116` | `_show_tab_model` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:152` | `_show_tab_model` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_model.py:191` | `_show_tab_model` | plotly_chart | à l'écran | `ml_song_predictions` | brut | plusieurs amonts | — | — |
| `views/youtube.py:116` | `show` | plotly_chart | à l'écran | `youtube_cumulative_views()` · `youtube_channel_history` | mixte | plusieurs amonts | profondeur | ?`youtube_video_stats` · ?`youtube_videos` |
| `views/youtube.py:274` | `show` | plotly_chart | à l'écran | `youtube_video_stats` · `youtube_videos` | brut | plusieurs amonts | — | ?`youtube_channel_history` |
| `utils/ml_widgets.py:168` | `render_classification_scorecard` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:351` | `_render_one_gauge` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:588` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:606` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:629` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/data_wrapped.py:264` | `_recap_spotify` | plotly_chart | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_audience` |
| `views/db_health.py:276` | `_show_heatmap` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/db_health.py:321` | `_show_cumulative` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/db_health.py:375` | `_show_batch_sizes` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/instagram.py:123` | `show` | plotly_chart | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/meta_ads_overview.py:536` | `_show_meta_ads` | plotly_chart | à l'écran | — | — | hors base | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_campaign_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:538` | `_show_meta_ads` | plotly_chart | à l'écran | — | — | hors base | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_campaign_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:540` | `_show_meta_ads` | plotly_chart | à l'écran | — | — | hors base | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_campaign_daily` · ?`v_meta_daily` |
| `views/meta_breakdowns.py:90` | `_render_performance` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:119` | `_render_engagement` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:129` | `_render_engagement` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/meta_creatives.py:476` | `_render_funnel` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:177` | `show` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:90` | `_tab_mrr` | plotly_chart | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | directe | — | — |
| `views/revenue_forecast.py:200` | `_tab_projection` | plotly_chart | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:262` | `_tab_ltv` | plotly_chart | à l'écran | — | — | hors base | — | ?`v_artist_monthly_revenue` |
| `views/spotify_s4a_combined.py:129` | `show` | plotly_chart | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/spotify_s4a_combined.py:184` | `show` | plotly_chart | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/spotify_s4a_combined.py:293` | `show` | plotly_chart | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/trigger_algo/_tab_explainability.py:101` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/trigger_algo/_tab_explainability.py:126` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/trigger_algo/_tab_explainability.py:160` | `_show_tab_explainability` | pyplot | un clic | — | — | hors base | — | — |
| `views/usage_analytics.py:56` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |
| `views/usage_analytics.py:69` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |
| `views/usage_analytics.py:83` | `show` | plotly_chart | à l'écran | `usage_events` | brut | directe | — | — |

## Les tuiles

`st.metric` n'est que 17 des 207 tuiles du produit ; les 190 autres passent par une poignée de colonne (`c1.metric`). Un inventaire qui n'aurait compté que le receveur `st` décrirait 8 % du produit.

**90 sur 207** portent une source établie ; **11** sont déclarées indéterminées et listées en tête ; 106 sont hors base par nature — la tranche a fini proprement sans lire la base — et 48 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `views/airflow_kpi.py:433` | `_section_insertion_test` | airflow_kpi.metric_dags_with_data | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:434` | `_section_insertion_test` | airflow_kpi.metric_dags_no_data | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:450` | `_section_insertion_test` | airflow_kpi.metric_rows | autre onglet | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/airflow_kpi.py:451` | `_section_insertion_test` | airflow_kpi.metric_days | autre onglet | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/alerts.py:286` | `_section_plan_evolution` | col.metric | à l'écran | — | — | indéterminée | receveur-inconnu | ?`subscription_plan_history` |
| ⚠️ `views/db_health.py:159` | `_show_health_table` | db_health.kpi_total_rows | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/db_health.py:160` | `_show_health_table` | db_health.kpi_stale | à l'écran | — | — | indéterminée | sql-dynamique | — |
| ⚠️ `views/imusician.py:303` | `show` | imusician.kpi_total | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| ⚠️ `views/imusician.py:304` | `show` | imusician.kpi_avg | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| ⚠️ `views/imusician.py:305` | `show` | imusician.kpi_months | à l'écran | — | — | indéterminée | sql-dynamique | ?`saas_artists` |
| ⚠️ `views/soundcloud.py:68` | `show` | soundcloud.kpi_last_update | à l'écran | — | — | indéterminée | appelants-multiples | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/admin.py:450` | `_render_costs` | admin.costs_metric_mrr | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/admin.py:451` | `_render_costs` | admin.costs_metric_margin | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | — |
| `views/admin.py:517` | `_render_supervision` | admin.metric_mrr | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` · ?`saas_users` |
| `views/admin.py:518` | `_render_supervision` | admin.metric_paying | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` · ?`saas_users` |
| `views/admin.py:519` | `_render_supervision` | admin.metric_arpu | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` · ?`saas_users` |
| `views/airflow_kpi.py:561` | `show` | airflow_kpi.metric_avg_invalid | à l'écran | `etl_run_log` | brut | plusieurs amonts | — | — |
| `views/billing.py:339` | `_show_admin_view` | billing.total_mrr | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` |
| `views/billing.py:340` | `_show_admin_view` | billing.paying_artists | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` |
| `views/billing.py:341` | `_show_admin_view` | ARPU | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | plusieurs amonts | — | ?`saas_artists` |
| `views/data_wrapped.py:247` | `_recap_spotify` | data_wrapped.recap_followers | à l'écran | `s4a_audience` | brut | plusieurs amonts | — | ?`v_s4a_song_daily` |
| `views/meta_ads_overview.py:141` | `_show_meta_ads` | meta_ads_overview.spend | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:142` | `_show_meta_ads` | meta_ads_overview.impressions | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:143` | `_show_meta_ads` | meta_ads_overview.link_clicks | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:144` | `_show_meta_ads` | CPM | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:145` | `_show_meta_ads` | CPC | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:146` | `_show_meta_ads` | meta_ads_overview.cpr_spotify | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:155` | `_show_meta_ads` | 💾 Saves | à l'écran | `v_meta_campaign_daily` · `meta_insights_engagement` | mixte | plusieurs amonts | — | ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:156` | `_show_meta_ads` | 🔄 Shares | à l'écran | `v_meta_campaign_daily` · `meta_insights_engagement` | mixte | plusieurs amonts | — | ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:157` | `_show_meta_ads` | meta_ads_overview.total_interactions | à l'écran | `v_meta_campaign_daily` · `meta_insights_engagement` | mixte | plusieurs amonts | — | ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:183` | `_show_meta_ads` | meta_ads_overview.impressions | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:184` | `_show_meta_ads` | meta_ads_overview.ad_clicks | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:186` | `_show_meta_ads` | meta_ads_overview.lp_views | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_ads_overview.py:189` | `_show_meta_ads` | meta_ads_overview.spotify_clicks | à l'écran | `v_meta_campaign_daily` | or | plusieurs amonts | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_daily` |
| `views/meta_cpr_optimizer.py:180` | `_render_detail_cards` | meta_cpr_optimizer.composite_score | un clic | `v_meta_campaign_daily` · `campaign_track_mapping` · `ml_song_predictions` | mixte | plusieurs amonts | — | — |
| `views/meta_cpr_optimizer.py:181` | `_render_detail_cards` | meta_cpr_optimizer.col_current_cpr | un clic | `v_meta_campaign_daily` · `campaign_track_mapping` · `ml_song_predictions` | mixte | plusieurs amonts | — | — |
| `views/meta_creatives.py:202` | `_render_kpi_row` | meta_creatives.total_spend | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:203` | `_render_kpi_row` | meta_creatives.best_cpr | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:204` | `_render_kpi_row` | meta_creatives.median_cpr | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/meta_creatives.py:205` | `_render_kpi_row` | meta_creatives.worst_cpr | à l'écran | `v_meta_creative_daily` | or | plusieurs amonts | — | — |
| `views/revenue_forecast.py:244` | `_tab_ltv` | revenue_forecast.ltv_global | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | plusieurs amonts | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:368` | `_tab_artist_forecast` | revenue_forecast.trend | à l'écran | `v_artist_monthly_revenue` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:617` | `_tab_artist_forecast` | revenue_forecast.meta_spend_metric | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:619` | `_tab_artist_forecast` | revenue_forecast.net_margin | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:628` | `_tab_artist_forecast` | revenue_forecast.meta_spend_metric | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:629` | `_tab_artist_forecast` | revenue_forecast.net_margin | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`ml_song_predictions` |
| `views/spotify_s4a_combined.py:84` | `show` | spotify_s4a_combined.kpi_last_update | à l'écran | `s4a_song_timeline` | brut | plusieurs amonts | — | ?`tracks` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_common/_lifecycle.py:100` | `_standardization_block` | — | à l'écran | `v_s4a_song_daily` | or | plusieurs amonts | — | — |
| `views/trigger_algo/_tab_budget_roi.py:232` | `_show_tab_budget_roi` | trigger_algo.roi.remaining_budget_metric | un clic | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:300` | `_show_tab_budget_roi` | R² | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:302` | `_show_tab_budget_roi` | trigger_algo.roi.slope_metric | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:304` | `_show_tab_budget_roi` | p-value | à l'écran | `get_monthly_roi_series()` | or | plusieurs amonts | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:93` | `_show_tab_global` | — | à l'écran | `s4a_songs_global` | brut | plusieurs amonts | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_song_timeline` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:97` | `_show_tab_global` | — | à l'écran | `v_s4a_song_daily` | or | plusieurs amonts | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_song_timeline` · ?`s4a_songs_global` |
| `views/trigger_algo/_tab_global.py:99` | `_show_tab_global` | — | à l'écran | `s4a_songs_global` | brut | plusieurs amonts | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_song_timeline` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:267` | `_show_tab_global` | trigger_algo.global.days_elapsed_metric | à l'écran | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_songs_global` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:271` | `_show_tab_global` | trigger_algo.global.cumul_streams_metric | à l'écran | `s4a_song_timeline` · `tracks` | brut | plusieurs amonts | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_songs_global` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_lifecycle.py:37` | `_show_tab_lifecycle` | trigger_algo.lifecycle.age_metric | à l'écran | `tracks` | brut | plusieurs amonts | — | — |
| `views/youtube.py:127` | `show` | youtube.kpi_total_views | à l'écran | `youtube_cumulative_views()` | or | plusieurs amonts | profondeur | ?`youtube_channel_history` · ?`youtube_video_stats` · ?`youtube_videos` |
| `utils/ml_widgets.py:132` | `render_classification_scorecard` | AUC | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:138` | `render_classification_scorecard` | ml_widgets.precision | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:139` | `render_classification_scorecard` | Recall | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:140` | `render_classification_scorecard` | F1 | à l'écran | — | — | hors base | — | — |
| `utils/ml_widgets.py:141` | `render_classification_scorecard` | Lift top-10% | à l'écran | — | — | hors base | — | — |
| `views/account.py:56` | `_section_profile` | account.username | à l'écran | — | — | hors base | — | — |
| `views/account.py:57` | `_section_profile` | account.role | à l'écran | — | — | hors base | — | — |
| `views/account.py:58` | `_section_profile` | account.email_verified | à l'écran | — | — | hors base | — | — |
| `views/admin.py:449` | `_render_costs` | admin.costs_metric_month | à l'écran | — | — | hors base | — | — |
| `views/admin.py:503` | `_render_supervision` | admin.metric_signups_7d | à l'écran | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:504` | `_render_supervision` | admin.metric_signups_30d | à l'écran | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:505` | `_render_supervision` | admin.metric_verified | à l'écran | `saas_users` | brut | directe | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/admin.py:506` | `_render_supervision` | admin.metric_active_artists | à l'écran | `saas_artists` | brut | directe | — | ?`artist_subscriptions` · ?`saas_users` · ?`subscription_plans` |
| `views/admin.py:749` | `_tab_users` | admin.metric_optin | à l'écran | — | — | hors base | — | ?`saas_artists` · ?`saas_users` |
| `views/airflow_kpi.py:204` | `_section_run_logs` | airflow_kpi.metric_total_lines | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:205` | `_section_run_logs` | airflow_kpi.metric_errors | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:206` | `_section_run_logs` | airflow_kpi.metric_warnings | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:300` | `_section_last_runs` | airflow_kpi.metric_total_dags | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:301` | `_section_last_runs` | airflow_kpi.metric_success | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:302` | `_section_last_runs` | airflow_kpi.metric_failures | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:303` | `_section_last_runs` | airflow_kpi.metric_never_run | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/airflow_kpi.py:440` | `_section_insertion_test` | airflow_kpi.metric_window | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:559` | `show` | airflow_kpi.metric_runs_24h | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:560` | `show` | airflow_kpi.metric_global_success | à l'écran | — | — | hors base | — | — |
| `views/airflow_kpi.py:562` | `show` | airflow_kpi.metric_failures_7d | à l'écran | — | — | hors base | — | — |
| `views/alerts.py:283` | `_section_plan_evolution` | alerts.total_artists | à l'écran | — | — | hors base | — | ?`subscription_plan_history` |
| `views/apple_music.py:33` | `show` | apple_music.kpi_songs | à l'écran | `apple_songs_performance` | brut | directe | — | ?`apple_songs_history` |
| `views/apple_music.py:57` | `show` | apple_music.kpi_streams | à l'écran | `apple_lifetime_plays()` | or | directe | — | ?`apple_songs_history` · ?`apple_songs_performance` |
| `views/apple_music.py:59` | `show` | apple_music.kpi_shazams | à l'écran | `apple_lifetime_shazams()` | or | directe | — | ?`apple_songs_history` · ?`apple_songs_performance` |
| `views/billing.py:162` | `_show_current_plan` | billing.metric_plan | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | directe | — | ?`saas_artists` |
| `views/billing.py:163` | `_show_current_plan` | billing.metric_price | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`saas_artists` · ?`subscription_plans` |
| `views/billing.py:164` | `_show_current_plan` | billing.metric_status | à l'écran | `artist_subscriptions` · `subscription_plans` | brut | directe | — | ?`saas_artists` |
| `views/data_wrapped.py:241` | `_recap_spotify` | data_wrapped.recap_total_streams | à l'écran | `get_total_streams_s4a()` | or | directe | — | ?`s4a_audience` · ?`v_s4a_song_daily` |
| `views/data_wrapped.py:243` | `_recap_spotify` | data_wrapped.recap_spotify_popularity | à l'écran | `get_spotify_popularity()` | or | directe | — | ?`s4a_audience` · ?`v_s4a_song_daily` |
| `views/data_wrapped.py:279` | `_recap_platforms` | data_wrapped.recap_youtube_views | à l'écran | `get_total_views_youtube()` | or | directe | — | — |
| `views/data_wrapped.py:281` | `_recap_platforms` | data_wrapped.recap_apple_plays | à l'écran | `get_total_plays_apple()` | or | directe | — | — |
| `views/data_wrapped.py:283` | `_recap_platforms` | data_wrapped.recap_soundcloud_plays | à l'écran | `get_total_plays_soundcloud()` | or | directe | — | — |
| `views/data_wrapped.py:287` | `_recap_platforms` | data_wrapped.recap_instagram_followers | à l'écran | `get_instagram_followers()` | or | directe | — | — |
| `views/data_wrapped.py:296` | `_recap_revenue` | data_wrapped.recap_imusician_revenue | à l'écran | `fmt_eur()` | or | directe | — | — |
| `views/data_wrapped.py:298` | `_recap_revenue` | data_wrapped.recap_meta_spend | à l'écran | `fmt_eur()` | or | directe | — | — |
| `views/data_wrapped.py:301` | `_recap_revenue` | data_wrapped.recap_roi | à l'écran | `get_roi_data()` | or | directe | — | — |
| `views/data_wrapped.py:592` | `show` | data_wrapped.field_listeners | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/data_wrapped.py:595` | `show` | data_wrapped.col_streams | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/data_wrapped.py:598` | `show` | data_wrapped.field_saves | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/data_wrapped.py:601` | `show` | data_wrapped.kpi_countries | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/db_health.py:157` | `_show_health_table` | db_health.kpi_active | à l'écran | — | — | hors base | — | — |
| `views/db_health.py:158` | `_show_health_table` | db_health.kpi_empty | à l'écran | — | — | hors base | — | — |
| `views/etl_logs.py:77` | `_section_kpis` | etl_logs.kpi_runs | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:78` | `_section_kpis` | etl_logs.kpi_success_rate | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:81` | `_section_kpis` | etl_logs.kpi_avg_duration | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/etl_logs.py:82` | `_section_kpis` | etl_logs.kpi_rows_inserted | à l'écran | — | — | hors base | — | ?`etl_run_log` |
| `views/etl_logs.py:83` | `_section_kpis` | etl_logs.kpi_failed_runs | à l'écran | `etl_run_log` | brut | directe | — | — |
| `views/hypeddit.py:169` | `_render_global_stats` | hypeddit.kpi_avg_visits | à l'écran | — | — | hors base | — | — |
| `views/hypeddit.py:170` | `_render_global_stats` | hypeddit.kpi_avg_clicks | à l'écran | — | — | hors base | — | — |
| `views/imusician.py:427` | `show` | imusician.roi_revenue | à l'écran | `fmt_eur()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:429` | `show` | imusician.roi_spend | à l'écran | `fmt_eur()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:441` | `show` | 📊 ROI | à l'écran | `get_roi_data()` | or | directe | — | ?`saas_artists` |
| `views/imusician.py:451` | `show` | 📊 ROI | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/imusician.py:456` | `show` | 📊 ROI | à l'écran | — | — | hors base | — | ?`saas_artists` |
| `views/instagram.py:36` | `show` | instagram.kpi_followers | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:37` | `show` | instagram.kpi_follows | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:38` | `show` | instagram.kpi_media | à l'écran | — | — | hors base | — | ?`instagram_daily_stats` · ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/instagram.py:39` | `show` | instagram.kpi_last_update | à l'écran | `instagram_daily_stats` | brut | directe | — | ?`instagram_media` · ?`instagram_media_insights` · ?`v_instagram_media_monthly` |
| `views/meta_ads_overview.py:192` | `_show_meta_ads` | meta_ads_overview.spotify_clicks | à l'écran | — | — | hors base | — | ?`meta_insights_engagement` · ?`meta_insights_performance_age` · ?`meta_insights_performance_country` · ?`meta_insights_performance_placement` · ?`v_meta_adset_daily` · ?`v_meta_campaign_daily` · ?`v_meta_daily` |
| `views/meta_breakdowns.py:72` | `_render_performance` | meta_breakdowns.total_spend | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:73` | `_render_performance` | meta_breakdowns.results | à l'écran | — | — | hors base | — | — |
| `views/meta_breakdowns.py:74` | `_render_performance` | meta_breakdowns.avg_cpr | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:128` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_analyzed | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:129` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_no_cpr | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:131` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_increase | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:132` | `_render_summary_kpi` | meta_cpr_optimizer.kpi_reduce | à l'écran | — | — | hors base | — | — |
| `views/meta_cpr_optimizer.py:182` | `_render_detail_cards` | meta_cpr_optimizer.col_budget | un clic | — | — | hors base | — | — |
| `views/perf_monitor.py:81` | `show` | perf_monitor.metric_last_render | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:83` | `show` | perf_monitor.metric_last_render | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:87` | `show` | perf_monitor.metric_db_ping | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:89` | `show` | perf_monitor.metric_db_ping | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:95` | `show` | perf_monitor.metric_ram | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:97` | `show` | perf_monitor.metric_ram | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:103` | `show` | perf_monitor.metric_cpu | à l'écran | — | — | hors base | — | — |
| `views/perf_monitor.py:105` | `show` | perf_monitor.metric_cpu | à l'écran | — | — | hors base | — | — |
| `views/referral.py:95` | `show` | referral.artists_referred | à l'écran | `referral_codes` | brut | directe | — | ?`referral_events` · ?`saas_artists` |
| `views/referral.py:96` | `show` | referral.free_months_earned | à l'écran | `saas_artists` | brut | directe | — | ?`referral_codes` · ?`referral_events` |
| `views/referral_admin.py:52` | `show` | referral_admin.metric_total_referrals | à l'écran | `referral_events` | brut | directe | — | ?`artist_subscriptions` · ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:53` | `show` | referral_admin.metric_converted | à l'écran | `artist_subscriptions` · `referral_events` | brut | directe | — | ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:54` | `show` | referral_admin.metric_conversion_rate | à l'écran | `artist_subscriptions` · `referral_events` | brut | directe | — | ?`referral_codes` · ?`saas_artists` · ?`subscription_plans` |
| `views/referral_admin.py:55` | `show` | referral_admin.metric_free_months | à l'écran | — | — | hors base | — | ?`artist_subscriptions` · ?`referral_codes` · ?`referral_events` · ?`saas_artists` · ?`subscription_plans` |
| `views/revenue_forecast.py:65` | `_tab_mrr` | revenue_forecast.mrr_total | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:66` | `_tab_mrr` | ARPU | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:67` | `_tab_mrr` | revenue_forecast.paying_artists | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:68` | `_tab_mrr` | revenue_forecast.pending_cancellations | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:175` | `_tab_projection` | revenue_forecast.mrr_final | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:176` | `_tab_projection` | revenue_forecast.arr_final | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:178` | `_tab_projection` | revenue_forecast.months_to_target | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:180` | `_tab_projection` | revenue_forecast.months_to_target | à l'écran | — | — | hors base | — | — |
| `views/revenue_forecast.py:242` | `_tab_ltv` | ARPU | à l'écran | `artist_subscriptions` · `saas_artists` · `subscription_plans` | brut | directe | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:243` | `_tab_ltv` | revenue_forecast.churn_monthly_metric | à l'écran | — | — | hors base | — | ?`v_artist_monthly_revenue` |
| `views/revenue_forecast.py:286` | `_tab_ltv` | revenue_forecast.avg_music_revenue | à l'écran | `v_artist_monthly_revenue` | or | directe | — | — |
| `views/revenue_forecast.py:287` | `_tab_ltv` | — | à l'écran | `v_artist_monthly_revenue` | or | directe | — | — |
| `views/revenue_forecast.py:323` | `_tab_artist_forecast` | 💿 iMusician | à l'écran | `v_artist_monthly_revenue` | or | directe | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:324` | `_tab_artist_forecast` | 🟢 DistroKid | à l'écran | `v_artist_monthly_revenue` | or | directe | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:325` | `_tab_artist_forecast` | 🎼 SACEM | à l'écran | `v_artist_monthly_revenue` | or | directe | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:367` | `_tab_artist_forecast` | revenue_forecast.avg_monthly_revenue | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:369` | `_tab_artist_forecast` | — | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:463` | `_tab_artist_forecast` | revenue_forecast.total_meta_spend | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:464` | `_tab_artist_forecast` | revenue_forecast.total_imusician_revenue | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:465` | `_tab_artist_forecast` | revenue_forecast.global_roi | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:616` | `_tab_artist_forecast` | revenue_forecast.projected_revenue | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:618` | `_tab_artist_forecast` | revenue_forecast.vps_infra | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/revenue_forecast.py:627` | `_tab_artist_forecast` | revenue_forecast.projected_revenue | à l'écran | — | — | hors base | — | ?`ml_song_predictions` |
| `views/sacem.py:79` | `show` | sacem.kpi_gross | à l'écran | `v_sacem_monthly` | or | directe | — | — |
| `views/sacem.py:80` | `show` | sacem.kpi_charges | à l'écran | `v_sacem_monthly` | or | directe | — | — |
| `views/sacem.py:81` | `show` | sacem.kpi_net | à l'écran | `v_sacem_monthly` | or | directe | — | — |
| `views/soundcloud.py:61` | `show` | soundcloud.kpi_plays | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:62` | `show` | soundcloud.kpi_likes | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:63` | `show` | soundcloud.kpi_reposts | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:66` | `show` | soundcloud.kpi_comments | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/soundcloud.py:67` | `show` | soundcloud.kpi_tracks | à l'écran | — | — | hors base | — | ?`soundcloud_tracks_daily` · ?`v_soundcloud_track_latest` |
| `views/spotify_s4a_combined.py:64` | `show` | spotify_s4a_combined.kpi_active_songs | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/spotify_s4a_combined.py:65` | `show` | spotify_s4a_combined.kpi_total_streams | à l'écran | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` · ?`tracks` |
| `views/spotify_s4a_combined.py:91` | `show` | spotify_s4a_combined.kpi_last_update | à l'écran | — | — | hors base | — | ?`s4a_song_timeline` · ?`tracks` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_common/_budget_roi.py:75` | `_show_budget_tier_selector` | trigger_algo.common.ar_selected_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_common/_budget_roi.py:76` | `_show_budget_tier_selector` | trigger_algo.common.ar_precision_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_common/_budget_roi.py:79` | `_show_budget_tier_selector` | trigger_algo.common.ar_lift_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_common/_budget_roi.py:82` | `_show_budget_tier_selector` | trigger_algo.common.ar_recall_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_common/_budget_roi.py:166` | `_show_budget_pacing_calculator` | trigger_algo.common.pacing_daily_metric | à l'écran | — | — | hors base | — | ?`v_meta_active_budget` |
| `views/trigger_algo/_common/_pi_gates.py:45` | `_show_pi_gate_section` | trigger_algo.common.pi_predicted_metric | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_tab_algo_streams.py:61` | `_show_tab_algo_streams` | 🟢 Discover Weekly | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:62` | `_show_tab_algo_streams` | 🩷 Release Radar | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:63` | `_show_tab_algo_streams` | 🟠 Radio | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_algo_streams.py:64` | `_show_tab_algo_streams` | trigger_algo.algostreams_total | à l'écran | — | — | hors base | — | ?`s4a_song_algo_outcomes` |
| `views/trigger_algo/_tab_budget_roi.py:54` | `_render_expected_value` | — | à l'écran | — | — | hors base | — | — |
| `views/trigger_algo/_tab_budget_roi.py:122` | `_show_tab_budget_roi` | trigger_algo.roi.lifetime_budget_metric | à l'écran | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:124` | `_show_tab_budget_roi` | trigger_algo.roi.spent_metric | à l'écran | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:126` | `_show_tab_budget_roi` | trigger_algo.roi.remaining_metric | à l'écran | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:131` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_stream_metric | à l'écran | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:153` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_stream_metric | à l'écran | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:233` | `_show_tab_budget_roi` | trigger_algo.roi.cost_per_submission_met | un clic | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_budget_roi.py:234` | `_show_tab_budget_roi` | trigger_algo.roi.possible_submissions_me | un clic | — | — | hors base | — | ?`imusician_monthly_revenue` · ?`track_popularity_history` · ?`v_artist_monthly_revenue` · ?`v_meta_active_budget` · ?`v_meta_daily` · ?`v_s4a_song_daily` |
| `views/trigger_algo/_tab_global.py:103` | `_show_tab_global` | trigger_algo.global.playlist_adds_metric | à l'écran | — | — | hors base | — | ?`ml_song_predictions` · ?`s4a_song_playlist_adds` · ?`s4a_song_timeline` · ?`s4a_songs_global` · ?`v_s4a_song_daily` |
| `views/usage_analytics.py:41` | `show` | usage_analytics.kpi_events | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/usage_analytics.py:42` | `show` | usage_analytics.kpi_sessions | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/usage_analytics.py:43` | `show` | usage_analytics.kpi_active_artists | à l'écran | — | — | hors base | — | ?`usage_events` |
| `views/useful_links.py:122` | `show` | Airflow UI | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:128` | `show` | Streamlit Dashboard | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:137` | `show` | REST API (FastAPI) | à l'écran | — | — | hors base | — | — |
| `views/useful_links.py:142` | `show` | API ReDoc | à l'écran | — | — | hors base | — | — |
| `views/youtube.py:125` | `show` | youtube.kpi_current_subs | à l'écran | — | — | hors base | — | ?`youtube_channel_history` · ?`youtube_video_stats` · ?`youtube_videos` |
| `views/youtube.py:129` | `show` | youtube.kpi_channel_views | à l'écran | — | — | hors base | — | ?`youtube_channel_history` · ?`youtube_video_stats` · ?`youtube_videos` |

## Les figures du PDF

Prises à leur site de câblage dans `_report.py` : les fonctions de `pdf_charts.py` reçoivent tout en paramètre, y trancher ne dirait rien.

**21 sur 29** portent une source établie ; **5** sont déclarées indéterminées et listées en tête ; 3 sont hors base par nature — la tranche a fini proprement sans lire la base — et 11 des attribuées ont plusieurs amonts.

| fichier:ligne | fonction | surface | visible | source établie | couche | confiance | motif | lu dans la même fonction (aucun lien prouvé) |
|---|---|---|---|---|---|---|---|---|
| ⚠️ `utils/pdf_exporter/_report.py:137` | `collect_report_data` | pdf_charts.streams_timeline | PDF | — | — | indéterminée | sans-appelant | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:160` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:163` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:166` | `collect_report_data` | pdf_charts.meta_breakdown_bars | PDF | — | — | indéterminée | sql-dynamique | ?`s4a_song_timeline` |
| ⚠️ `utils/pdf_exporter/_report.py:181` | `collect_report_data` | pdf_charts.pi_gate | PDF | — | — | indéterminée | appelants-multiples | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:143` | `collect_report_data` | pdf_charts.platform_evolution | PDF | `apple_yearly_series()` · `cumulative_by_platform()` · `daily_streams_by_platform()` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:145` | `collect_report_data` | pdf_charts.j28_trajectory | PDF | `v_s4a_song_daily` · `tracks` | mixte | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:147` | `collect_report_data` | pdf_charts.top_songs_bar | PDF | `v_s4a_song_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:150` | `collect_report_data` | pdf_charts.youtube_top_videos_bar | PDF | `v_platform_totals` · `youtube_channel_history` · `youtube_video_stats` · `youtube_videos` | mixte | plusieurs amonts | profondeur | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:152` | `collect_report_data` | pdf_charts.top_songs_bar | PDF | `apple_songs_performance` | brut | plusieurs amonts | profondeur | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:159` | `collect_report_data` | pdf_charts.hypeddit_combo | PDF | `v_hypeddit_daily` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:169` | `collect_report_data` | pdf_charts.revenue_forecast_chart | PDF | `v_artist_monthly_revenue` | or | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:170` | `collect_report_data` | pdf_charts.indexed_lines | PDF | `v_meta_daily` · `v_s4a_song_daily` · `track_popularity_history` | mixte | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:182` | `collect_report_data` | pdf_charts.apple_timeline | PDF | `apple_songs_history` | brut | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:183` | `collect_report_data` | pdf_charts.sc_multiaxis | PDF | `soundcloud_tracks_daily` | brut | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:187` | `collect_report_data` | pdf_charts.youtube_channel_growth | PDF | `youtube_cumulative_views()` · `youtube_channel_history` | mixte | plusieurs amonts | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:138` | `collect_report_data` | pdf_charts.platform_breakdown | PDF | `platform_totals()` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:144` | `collect_report_data` | pdf_charts.ml_probabilities | PDF | `tracks` | brut | portée (1 saut) | sans-appelant | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:146` | `collect_report_data` | pdf_charts.roi_breakeven | PDF | `get_roi_data()` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:151` | `collect_report_data` | pdf_charts.soundcloud_top_bar | PDF | — | — | hors base | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:156` | `collect_report_data` | pdf_charts.instagram_followers_line | PDF | `instagram_daily_stats` | brut | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:158` | `collect_report_data` | pdf_charts.meta_campaigns_bar | PDF | `v_meta_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:178` | `collect_report_data` | pdf_charts.playlist_adds_bars | PDF | `s4a_song_playlist_adds` | brut | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:179` | `collect_report_data` | pdf_charts.meta_funnel | PDF | — | — | hors base | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:180` | `collect_report_data` | pdf_charts.meta_daily | PDF | `v_meta_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:184` | `collect_report_data` | pdf_charts.ig_engagement | PDF | — | — | hors base | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:185` | `collect_report_data` | pdf_charts.s4a_cumulative | PDF | `v_s4a_song_daily` | or | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:186` | `collect_report_data` | pdf_charts.s4a_audience_evolution | PDF | `s4a_audience` | brut | directe | — | ?`s4a_song_timeline` |
| `utils/pdf_exporter/_report.py:188` | `collect_report_data` | pdf_charts.song_timeline | PDF | `v_s4a_song_daily` | or | portée (1 saut) | sans-appelant | ?`s4a_song_timeline` |

## Les plateformes

Une ligne par plateforme. « Lectures brutes » compte les lectures de ses tables de fait **hors des portes** : ce n'est pas un compte de défauts — un catalogue de titres ou une date de dernier relevé n'a rien à centraliser — mais c'est là que la prochaine divergence naîtra.

| plateforme | tables de fait | vues or qui la définissent | lectures des vues or | lectures brutes |
|---|---|---|---|---|
| Apple Music | `apple_songs_history` · `apple_songs_performance` | `gold_apple_lifetime` · `v_platform_totals` | 16 | 7 |
| Hypeddit | `hypeddit_daily_stats` | `v_hypeddit_daily` | 3 | 1 |
| Instagram | `instagram_daily_stats` · `instagram_media` | `v_instagram_media_monthly` | 2 | 8 |
| Meta Ads | `meta_ads` · `meta_adsets` · `meta_campaigns` · `meta_insights` · `meta_insights_performance` · `meta_insights_performance_day` | `v_meta_active_budget` · `v_meta_adset_daily` · `v_meta_campaign_daily` · `v_meta_creative_daily` · `v_meta_daily` · `v_meta_spend_totals` | 34 | 21 |
| Revenu | `distrokid_monthly_revenue` · `imusician_monthly_revenue` · `sacem_statement` | `v_artist_monthly_revenue` · `v_sacem_monthly` | 11 | 4 |
| SoundCloud | `soundcloud_tracks_daily` | `v_platform_levels` · `v_platform_totals` · `v_soundcloud_track_latest` | 20 | 6 |
| Spotify S4A | `s4a_audience` · `s4a_song_timeline` · `s4a_songs_global` | `v_platform_levels` · `v_platform_totals` · `v_s4a_song_daily` | 47 | 32 |
| YouTube | `youtube_channel_history` · `youtube_video_stats` | `v_platform_levels` · `v_platform_totals` | 17 | 9 |

## Les cliquets

**18 valeurs gelées** dans 13 fichiers. Un cliquet pose deux questions, et la seconde est celle qu'on oublie : le plafond est-il **serré** (égal à la mesure — un plafond au-dessus est du mou qui autorise en silence ce qu'il interdit), et la population est-elle **plancherée** ? « Zéro indéterminée » sur zéro figure est vrai et ne dit rien.

**0 sans test de non-vacuité** et **0 sans trace de mutation** dans leur fichier. Une trace de mutation est une phrase qui dit que le garde a été VU rouge sur le défaut qu'il vise ; sans elle, rien ne distingue un garde d'un test qui ne peut pas échouer.

Les deux colonnes de trou sont détectées sur le TEXTE du fichier de test (une phrase de mutation, un nom de test de non-vacuité) : un faux négatif est possible, il se corrige en écrivant la phrase.

| fichier | constante | valeur gelée | non-vacuité | trace de mutation |
|---|---|---|---|---|
| `test_a_chart_is_bounded_by_the_period_it_announces.py` | `_MAX_UNBOUNDED_FIGURES` | 0 | — | — |
| `test_a_failed_read_is_not_an_absence.py` | `_CEILING` | 5 | — | — |
| `test_a_page_asks_the_same_question_once.py` | `_MAX_QUERIES` | 2 entrées | — | — |
| `test_a_sql_identifier_comes_from_a_closed_set.py` | `_MAX_UNSOURCED` | 0 | — | — |
| `test_a_view_opens_on_one_decision.py` | `_MAX_FIRST_SCREEN` | 5 | — | — |
| `test_chart_budget.py` | `_BUDGET` | 7 entrées | — | — |
| `test_the_bronze_boundary_only_tightens.py` | `_CEILING` | 108 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MAX_ORPHANS` | 3 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MIN_TOTAL` | 296 | — | — |
| `test_the_error_class_families_only_improve.py` | `_MIN_FAMILIES` | 17 | — | — |
| `test_the_gold_coverage_only_improves.py` | `_CEILING` | 11 entrées | — | — |
| `test_the_gold_coverage_only_improves.py` | `_FLOOR` | 10 entrées | — | — |
| `test_the_metrics_layer_only_grows.py` | `_CEILING` | 8 entrées | — | — |
| `test_the_tenant_guard_is_written_once.py` | `_MAX_OPEN_CODED` | 0 | — | — |
| `test_the_visual_rules_only_tighten.py` | `_MAX_SECONDARY_AXES` | 0 | — | — |
| `test_the_visual_rules_only_tighten.py` | `_MAX_LITERAL_KEYS` | 119 | — | — |
| `test_the_websocket_survives_the_proxy.py` | `_MAX_SAFE_INTERVAL_S` | 60 | — | — |
| `test_the_websocket_survives_the_proxy.py` | `_MIN_SANE_INTERVAL_S` | 5 | — | — |

## Les classes d'erreur

**301 classes** au catalogue. Le regroupement en familles vit dans `error-class-families.md` ; ici on ne pose qu'une question, celle qui se périme : **le garde que la classe nomme existe-t-il encore ?** Une classe `guarded` dont le garde a été supprimé se lit exactement comme une classe gardée.

**fixed** : 10· **guarded** : 275· **open** : 4· **reported** : 12

**0 classe(s) nomment un fichier de garde qui n'existe plus** et **11** ne nomment aucun chemin (leur garde est une règle transverse, un hook, ou rien).

_Aucune classe ne nomme un garde disparu._


Sans chemin de garde : `db-connection-per-show` · `view-session-adoption` · `snapshot-fixture-hook-reflow` · `dag-trigger-without-tenant-scope` · `ast-guard-blind-to-bom` · `migration-ahead-of-its-code` · `repo-copy-of-a-config-is-not-what-runs` · `mermaid-block-does-not-render` · `guard-anchored-on-shape-not-question` · `a-filtered-test-run-proves-nothing` · `a-guard-that-sees-the-binding-not-the-application`.


## Ce qui n'est gardé par rien

La question du livrable qui restait sans réponse : **quelles erreurs pourrait-on encore faire ?** Une case vide est une plateforme pour laquelle aucun garde de cette famille ne lit une seule de ses relations — donc un test à écrire, et c'est la liste des tests CI à intégrer.

Seules les familles de forme PLATEFORME sont ici. Un document périmé ou un seuil écrit d'instinct n'appartiennent à aucune plateforme ; les compter ainsi fabriquerait cent faux trous, et un livrable qui crie cent fois est un livrable que personne ne lit.

Le chiffre d'une case est le nombre de fichiers de garde qui NOMMENT une relation de cette plateforme dans un littéral SQL — jamais dans un commentaire : ce dépôt a pris quatre gardes au vert sur leur propre commentaire.

| famille | Apple Music | Hypeddit | Instagram | Meta Ads | Revenu | SoundCloud | Spotify S4A | YouTube |
|---|---|---|---|---|---|---|---|---|
| [le-locataire](error-class-families.md#le-locataire) | 2 | 1 | 2 | 2 | 2 | 3 | 4 | 3 |
| [un-cumul-pris-pour-un-quotidien](error-class-families.md#un-cumul-pris-pour-un-quotidien) | 2 | 1 | 1 | 1 | 1 | 4 | 3 | 3 |
| [deux-surfaces-deux-nombres](error-class-families.md#deux-surfaces-deux-nombres) | 3 | 1 | 2 | 3 | 2 | 3 | 3 | 3 |
| [une-erreur-avalée-devient-une-absence](error-class-families.md#une-erreur-avalée-devient-une-absence) | 2 | 1 | 2 | 1 | 1 | 2 | 4 | 2 |
| [un-nombre-affirmé-qui-n-a-pas-été-mesuré](error-class-families.md#un-nombre-affirmé-qui-n-a-pas-été-mesuré) | 2 | 1 | 2 | 1 | 1 | 2 | 2 | 2 |

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

**12 paires** de définitions or que rien n'oblige à coïncider sauf la donnée elle-même. ADR-019 garantit qu'une métrique a une seule **définition** ; que deux définitions censées coïncider coïncident est une propriété des DONNÉES, vérifiée chaque nuit par `alert_monitor.check_gold_invariants` et à chaque exécution de la suite par `tests/test_the_gold_layer_agrees_with_itself.py`.

Le défaut qui a fait naître cette section : `meta_insights_performance` et `meta_insights_performance_day` répondent à la même question et divergeaient d'un **facteur deux** en production, pendant des semaines. Chaque côté était cohérent avec lui-même ; personne ne comparait.

**0 objet(s) or ne sont touchés par aucun invariant** : aucun. Un objet que rien ne confronte peut dériver en silence — c'est le premier à le faire.

| invariant | un côté | l'autre |
|---|---|---|
| `meta_spend_two_grains` | `v_meta_daily` | `v_meta_campaign_daily` |
| `meta_spend_creative_vs_adset` | `v_meta_creative_daily` | `v_meta_adset_daily` |
| `meta_spend_totals_vs_daily` | `v_meta_spend_totals` | `v_meta_daily` |
| `spotify_total_vs_song_grain` | `v_platform_totals[spotify]` | `v_s4a_song_daily` |
| `soundcloud_total_vs_track_grain` | `v_platform_totals[soundcloud]` | `v_soundcloud_track_latest` |
| `sacem_revenue_vs_statement_grain` | `v_artist_monthly_revenue[sacem]` | `v_sacem_monthly[repartition]` |
| `apple_total_vs_function` | `v_platform_totals[apple]` | `gold_apple_lifetime()` |
| `levels_vs_total_youtube` | `v_platform_levels[youtube] au dernier jour` | `v_platform_totals[youtube]` |
| `levels_vs_total_soundcloud` | `v_platform_levels[soundcloud] au dernier jour` | `v_platform_totals[soundcloud]` |
| `hypeddit_view_loses_no_row` | `v_hypeddit_daily` | `hypeddit_daily_stats` |
| `meta_active_budget_matches_its_filter` | `v_meta_active_budget` | `meta_campaigns[status=ACTIVE]` |
| `instagram_view_loses_no_post_that_has_a_date` | `v_instagram_media_monthly` | `instagram_media[timestamp non nul]` |

## Les étapes de la CI

**12 étapes**, dont **12 bloquantes**. Lu dans `.github/workflows/ci.yml`, jamais récité — une liste d'étapes écrite à la main décrit la CI qu'on croit avoir.

⚠️ Une CI rouge cache tout ce qui la suit : ce dépôt l'a mesuré deux fois (8 exécutions bloquées à l'étape 3/8, puis 27 à l'étape 10/15). C'est `if: !cancelled()` qui l'a arrêté, pas la leçon écrite entre les deux.

| # | étape | ce qu'elle lance | rôle |
|---|---|---|---|
| 1 | Install uv | — | bloquante |
| 2 | Set up Python 3.11 | — | bloquante |
| 3 | Install system dependencies (build tools for any wheel-less package) | — | bloquante |
| 4 | Install dependencies from lockfile | sync | bloquante |
| 5 | Manifest consistency (blocking) | check_manifest_consistency.py | bloquante |
| 6 | Lint (ruff) — full project (blocking) | ruff check | bloquante |
| 7 | REX integrity + deterministic error-class guards (blocking) | validate_rex.py, audit_runner.py, check_config_refs.py, check_ci_waste.py, gold_coverage.py, error_class_famil | bloquante |
| 8 | Error-class schema completeness | audit_runner.py | bloquante |
| 9 | Provision Postgres (schema + migrations) | test_suite_runs_against_two_tenants.py | bloquante |
| 10 | Mint a throwaway Fernet key for this run | — | bloquante |
| 11 | Run tests | pytest | bloquante |
| 12 | Upload coverage artifact | — | bloquante |

## Ce qui n'est atteint par rien

C'est la vraie valeur de ce document. Les deux tableaux ne disent pas la même chose et il ne faut pas les lire pareil.

**Vues or que rien ne lit dans `src/` :** aucune. Une vue or sans lecteur est du travail gelé — soit la surface qui devait la lire ne l'a jamais fait, soit la vue n'avait pas lieu d'être.

Le second tableau liste les **tables brutes encore lues hors des portes**, alors qu'une vue or couvre le même grain. Ce n'est pas une liste de défauts : une lecture non agrégée — un catalogue, une date de dernier relevé, une liste de titres — n'a pas de définition à centraliser.

**La colonne qui compte est « dont hors cliquet ».** `tests/test_the_metrics_layer_only_grows.py` tient les agrégats à zéro, mais seulement sur les répertoires qu'il nomme `src/dashboard/views` · `src/dashboard/utils` · `src/api/routers` et sur les tables de sa propre liste de faits. Un agrégat hors de ces deux périmètres n'est gardé par rien. C'est exactement la forme du défaut du 2026-09-12 : le cliquet disait zéro, douze agrégats vivaient dans un répertoire qu'il ne nommait pas. Ces lignes-là sont les suivantes à regarder — chacune est soit un agrégat à repointer, soit un `MIN`/`MAX`/`COUNT` d'inventaire qui n'a rien à centraliser.

| table brute | vue or qui la couvre | lectures | agrégeantes | dont hors cliquet | où (les hors-cliquet d'abord) |
|---|---|---|---|---|---|
| `apple_songs_performance` | `gold_apple_lifetime` | 3 | 1 | 0 | dashboard/views/apple_music.py:28 |
| `distrokid_monthly_revenue` | `v_artist_monthly_revenue` | 1 | 1 | 0 | utils/distrokid_rollup.py:59 |
| `hypeddit_daily_stats` | `v_hypeddit_daily` | 1 | — | 0 | dashboard/views/meta_x_spotify.py:135 |
| `imusician_monthly_revenue` | `v_artist_monthly_revenue` | 2 | 1 | 0 | utils/imusician_rollup.py:42 |
| `instagram_media` | `v_instagram_media_monthly` | 1 | — | 0 | dashboard/views/instagram.py:282 |
| `meta_ads` | `v_meta_adset_daily` | 5 | 3 | 0 | dashboard/views/meta_creatives.py:593 · dashboard/views/meta_mapping/_campaigns.py:41 · dashboard/views/trigger_algo/_common/_budget_roi.py:227 |
| `meta_adsets` | `v_meta_adset_daily` | 3 | 1 | 0 | dashboard/views/meta_mapping/_campaigns.py:41 |
| `meta_campaigns` | `v_meta_active_budget` | 10 | 7 | 0 | dashboard/views/meta_creatives.py:593 · dashboard/views/meta_mapping/_campaigns.py:140 · dashboard/views/meta_mapping/_campaigns.py:155 · dashboard/views/meta_mapping/_campaigns.py:24 · dashboard/views/meta_mapping/_campaigns.py:41 · dashboard/views/trigger_algo/_common/_budget_roi.py:227 · utils/freshness_monitor.py:180 |
| `meta_insights` | `v_meta_adset_daily` | 1 | 1 | 0 | dashboard/views/meta_creatives.py:593 |
| `meta_insights_performance` | `v_meta_campaign_daily` | 1 | 1 | 0 | dashboard/views/meta_mapping/_campaigns.py:190 |
| `meta_insights_performance_day` | `v_meta_campaign_daily` | 6 | 5 | 0 | collectors/_meta_insight_fetch.py:59 · dashboard/views/imusician.py:36 · dashboard/views/imusician.py:45 · dashboard/views/meta_x_spotify.py:57 · dashboard/views/meta_x_spotify.py:80 |
| `s4a_song_timeline` | `v_s4a_song_daily` | 20 | 4 | 0 | api/routers/streams.py:87 · dashboard/utils/pdf_exporter/_report.py:75 · dashboard/utils/setup_completion.py:248 · dashboard/views/spotify_s4a_combined.py:41 |
| `sacem_statement` | `v_sacem_monthly` | 1 | — | 0 | dashboard/views/sacem.py:26 |
| `soundcloud_tracks_daily` | `v_soundcloud_track_latest` | 6 | 1 | 0 | dashboard/views/soundcloud.py:38 |
| `youtube_video_stats` | `v_platform_levels` | 6 | 3 | 0 | dashboard/utils/pdf_exporter/_collectors.py:249 · dashboard/views/youtube.py:183 · dashboard/views/youtube.py:201 |

### Les agrégats DÉCLARÉS

**11 couples (fichier, table)** agrègent une table de fait hors de tout cliquet, délibérément. La frontière est nette : un COMPTE, une DATE ou une CONCATÉNATION de noms répond « qu'y a-t-il » ; une somme d'argent, d'écoutes, de vues ou de clics répond « combien » et appartient à la couche or, sans exception.

Chaque déclaration est vérifiée : le site doit encore exister et encore agréger cette table. Une déclaration qui survit à ce qu'elle déclarait est du budget pour la prochaine occurrence.

| fichier | table | pourquoi ce n'est pas une métrique |
|---|---|---|
| `collectors/_meta_insight_fetch.py` | `meta_insights_performance_day` | MAX(day_date) : le point de reprise de la collecte incrémentale. Un collecteur n'est pas une surface, et cette date n'est affichée nulle part. |
| `dashboard/views/meta_creatives.py` | `meta_ads` | même requête : le COUNT des créatives d'une campagne dont les insights manquent. Un décompte de diagnostic, jamais affiché comme une mesure. |
| `dashboard/views/meta_creatives.py` | `meta_campaigns` | `_QUERY_UNCOLLECTED` : COUNT(DISTINCT ad_id) et un `HAVING SUM(spend) = 0` qui SÉLECTIONNE les campagnes sans détail par créative. Le montant affiché à côté vient de `v_meta_daily` ; ici la somme est un prédicat, pas un nombre — et elle doit porter sur la table de fait, puisque la question est précisément « cette table est-elle vide pour cette campagne ». |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_ads` | string_agg des noms de créatives, pour reconnaître de quelle sortie parle une campagne. Un nom n'est pas une mesure. |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_adsets` | MIN/MAX des dates d'activité d'un ad set, pour comparer à la date de sortie du titre. Une fenêtre, pas un chiffre affiché. |
| `dashboard/views/meta_mapping/_campaigns.py` | `meta_campaigns` | catalogue de campagnes à associer : MAX(start_time), string_agg de noms, bool_or d'un marqueur de rejet. Aucun montant, aucune performance. |
| `dashboard/views/trigger_algo/_common/_budget_roi.py` | `meta_ads` | même requête que ci-dessus : la jointure vers les créatives sert à lire leur call_to_action, jamais à sommer. |
| `dashboard/views/trigger_algo/_common/_budget_roi.py` | `meta_campaigns` | string_agg(DISTINCT call_to_action) — l'inventaire des appels à l'action d'une campagne, à côté de sa performance qui, elle, vient de la couche or. |
| `utils/distrokid_rollup.py` | `distrokid_monthly_revenue` | COUNT(*) des mois issus d'un import, renvoyé par le rollup qui vient de les écrire. C'est un accusé de réception, pas un revenu. |
| `utils/freshness_monitor.py` | `meta_campaigns` | count(*) FILTER (status = 'ACTIVE') — une sonde de santé. Elle demande « ce locataire a-t-il des campagnes », pas « combien ont-elles coûté ». |
| `utils/imusician_rollup.py` | `imusician_monthly_revenue` | idem : le compte des mois que le rollup vient d'écrire. |

## Les chiffres gelés

Ces compteurs sont écrits par la machine. Le cliquet `tests/test_the_gold_coverage_only_improves.py` les compare à un plafond posé **à** la mesure, jamais au-dessus.

<!-- gold-coverage-figures: total=89 unknown=7 -->
<!-- gold-coverage-tiles: total=207 unknown=11 -->
<!-- gold-coverage-pdf: total=29 unknown=5 -->
<!-- gold-coverage-gold-objects: total=15 orphans=0 -->
<!-- gold-coverage-unguarded-aggregates: total=0 -->
<!-- gold-coverage-ratchets: total=18 without_nonvacuity=0 without_mutation=0 -->
<!-- gold-coverage-error-classes: total=301 guard_missing=0 guard_unnamed=11 -->
<!-- gold-coverage-guard-matrix: cells=40 holes=0 -->
<!-- gold-coverage-invariants: pairs=12 unreconciled=0 -->
<!-- gold-coverage-ci: steps=12 blocking=12 -->

<!-- gold-coverage: sha256=0fdb2d0e16f2580995e3e16bf9fd02efe3389a3bc299e433e5696edc7cbe87a7 -->
