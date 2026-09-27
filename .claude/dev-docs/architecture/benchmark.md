# Benchmark d'architecture — actuel contre théorique

> **Généré** par `make arch-benchmark` depuis `domains.yaml` et `requirements.yaml`.
> Ne pas éditer à la main : corriger le catalogue, puis régénérer.

**65 exigences** sur **20 domaines** (carte : 24). conforme : 46 · partiel : 13 · absent : 6 · non-mesure : 0 · RÉGRESSION : 0 · sans preuve rejouable : 11

## Collecteurs API (`collect`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-COLLECT-01 | Un collecteur lève ; jamais de retour vide silencieux dans un except | conforme | `tests/test_the_collector_audit_sees_a_silent_return.py` ✅ | — | — |

## Orchestration Airflow et fan-out par locataire (`orchestration`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ORCH-01 | La durée d'une collecte ne croît pas linéairement avec le nombre de locataires — un locataire lent ne retarde pas les autres (fan-out par locataire) | absent | `—`  | Kleppmann, Designing Data-Intensive Applications p.39 (repenser à chaque ordre de grandeur); Golding, Multi-Tenant SaaS p.449 (noisy neighbor) | 5 DAGs bouclent sur les locataires dans une seule tâche ; meta p95 1 953 s pour ~1 locataire réel, timeout 3 h dépassé vers 10× → R266 |
| REQ-ORCH-02 | Chaque DAG de collecte enregistre le résultat de chaque locataire (succès, échec, sauté) | conforme | `tests/test_every_collection_dag_records_its_tenants.py::test_a_collection_dag_records_each_tenant_outcome` ✅ | — | — |
| REQ-ORCH-03 | Les quotas d'API partagés (YouTube, Meta) sont budgétés par locataire et leur consommation est mesurée | absent | `—`  | Golding p.341 (métriques de consommation par locataire) | — → R266 |
| REQ-ORCH-04 | La collecte d'une plateforme part dès que ses identifiants sont validés, sans attendre la nuit | conforme | `tests/test_credentials_save_triggers_the_right_dag.py::test_each_tab_starts_only_its_own_collection` ✅ | — | — |

## Bronze — tables de collecte et schéma (`bronze`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-BRONZE-01 | Tout upsert vise un index unique existant et nomme son locataire | conforme | `tests/test_an_upsert_targets_an_index_that_exists.py::test_every_literal_upsert_target_has_a_matching_unique_index` ✅ | Densmore, Data Pipelines Pocket Reference p.55 (chargement incrémental) | — |
| REQ-BRONZE-02 | Rien d'écrasé n'est perdu — l'historique d'une donnée réécrite est conservé automatiquement | conforme | `make schema-check-local` ✅ | — | — |

## Argent — séries conformées (`silver`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-SILVER-01 | La couche argent a une identité mécanique — on sait, par le nom ou un registre, quelle vue est argent et laquelle est or | conforme | `tests/test_every_object_has_a_layer.py::test_every_view_is_gold_or_its_layer_is_declared_not_vacuous` ✅ | — | R258 : chaque vue créée par une migration est or (registre), l argent est déclaré par module Python (ADR-019) → R258 |

## Or — une définition par KPI (`gold`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-GOLD-01 | Une métrique = une définition canonique = une vue or, déclarée au registre avec son sens (flux, cumul, niveau) | conforme | `tests/test_every_metric_is_registered.py::test_every_read_gold_object_is_registered_and_no_entry_is_dead` ✅ | Reis & Housley, Fundamentals of Data Engineering p.482 (metrics layer) | — |
| REQ-GOLD-02 | Chaque KPI porte définition, source(s), formule, granularité, fenêtre, et ses tests de qualité se lisent | conforme | `tests/test_every_metric_is_registered.py::test_the_untested_metrics_only_become_fewer` ✅ | Reis & Housley p.482 | corrigé le 2026-09-27 (critic R258) : formula, grain et window existent dans le registre ; les tests d'une métrique sont CALCULÉS par gold_coverage, sous cliquet |
| REQ-GOLD-03 | Un graphique ou une tuile ne lit que l'or ; le nombre de lectures du brut ne fait que baisser | partiel | `tests/test_the_bronze_boundary_only_tightens.py::test_the_bronze_boundary_never_loosens` ✅ | — | 18/64 figures et 44/162 tuiles lisent encore du brut (plafond de paires 66) — gold-coverage.md → R280 |
| REQ-GOLD-04 | Deux définitions censées coïncider sont comparées sur les vraies données, et l'écart alerte | conforme | `tests/test_the_gold_layer_agrees_with_itself.py::test_every_gold_invariant_holds_on_the_real_data` ✅ | Moses et al., Data Quality Fundamentals p.152 (piliers de l'observabilité) | — |
| REQ-GOLD-05 | Ce que la figure DESSINE est contrôlé après sa lecture or (taux ≤ 100 %, cumul qui ne retombe pas, pas deux barres sous un nom) | conforme | `tests/test_a_chart_number_is_checked_after_its_gold_read.py::test_the_detector_sees_the_defect_it_is_written_for` ✅ | — | — |

## Qualité et observabilité des données (`data-quality`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-DQ-01 | Sept familles de contrôles automatiques : doublons, valeurs impossibles, ruptures temporelles, variations anormales, divergences entre plateformes, mapping, données manquantes | conforme | `tests/test_every_quality_check_has_a_category.py` ✅ | Moses et al. p.135 et p.152 | R258 : les trois manques de R230 sont des contrôles du soir (borne par nature, doublons artist_history, campagne sans titre) → R258 |
| REQ-DQ-02 | Une anomalie d'ingestion se mesure en lignes attendues × locataires contre lignes reçues, avec seuil | conforme | `tests/test_an_ingestion_gap_is_expected_against_received.py` ✅ | — | — |
| REQ-DQ-03 | Un défaut de donnée est corrigé à sa cause, pas maquillé ; une absence n'est jamais dessinée comme un zéro | conforme | `tests/test_a_figure_never_draws_a_zero_it_did_not_measure.py` ✅ | — | — → R206 |

## Filtres modulaires (`filters`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-FILTER-01 | Une seule couche de filtres (période, titre, plateforme, compte, campagne) ; aucune vue n'écrit son propre filtre | conforme | `tests/test_a_view_filters_through_the_shared_layer.py::test_no_view_writes_its_own_period_filter` ✅ | — | R259 : smart_date_range retiré (span_period_filter), les vues Meta importent le compte par filters.py → R259 |
| REQ-FILTER-02 | Le filtre de période s'ouvre par défaut sur « depuis la dernière sortie », dans toute l'app | conforme | `tests/test_the_period_filter_defaults_to_the_last_release.py::test_the_layer_defaults_to_the_last_release` ✅ | — | chaque vue de plateforme passe last_release elle-même, mais le défaut de la couche partagée reste « current » (src/dashboard/utils/period_filter.py _default_preset) et aucun test ne l'exige → R259 |
| REQ-FILTER-03 | Élargir n'importe quel filtre ne fait jamais planter la vue | conforme | `tests/test_a_widened_filter_still_renders.py::test_widening_every_filter_does_not_raise` ✅ | — | — |
| REQ-FILTER-04 | Toute vue qui trace une série dans le temps offre le filtre de période commun | conforme | `tests/test_the_period_filter_defaults_to_the_last_release.py::test_every_view_drawing_a_daily_series_goes_through_the_shared_filter` ✅ | — | R259 : meta_ads_overview filtré (ancré au lancement des campagnes) ; meta_breakdowns n'a pas de dimension date, meta_cpr_optimizer ne trace pas de série → R259 |

## Porte de dessin — légendes, palette, Pareto (`chart-door`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-CHART-01 | Tout graphique passe par une seule porte (légende, glossaire, palette) | conforme | `tests/test_every_chart_goes_through_the_door.py::test_no_chart_walks_around_the_door` ✅ | Few, Information Dashboard Design p.74 (attributs visuels constants) | — |
| REQ-CHART-02 | Une plateforme a UNE couleur dans toute l'app (Meta bleu, Spotify vert, SoundCloud orange…) ; aucune couleur de plateforme en dur dans les vues | conforme | `tests/test_a_platform_colour_has_one_definition.py::test_no_new_hardcoded_platform_colour` ✅ | Few p.74 | R260 : 42 → 0 couleur de plateforme en dur, PDF compris ; une palette unique pour DW/RR/Radio → R260 |
| REQ-CHART-03 | Tri Pareto par défaut sur les barres par catégorie | conforme | `tests/test_a_nominal_bar_chart_is_sorted_pareto.py::test_nominal_categories_are_sorted_by_total` ✅ | — | R260 : Pareto par défaut sur les catégories nominales ; dates, tranches, mois et entonnoirs jamais réordonnés → R260 |
| REQ-CHART-04 | Aucune redondance — une page ne dessine pas deux fois la même mesure | conforme | `tests/test_a_tile_does_not_repeat_a_chart.py::test_every_tile_sharing_a_charts_sources_was_reviewed` ✅ | — | R258 : figures (empreinte mesure) et tuiles (empreinte page × sources, 5 groupes revus, 0 répétition) → R258 |

## Formats — tuiles, tableaux, nombres, dates (`formats`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-FORMAT-01 | Un formateur unique pour nombres, monnaie, pourcentages et dates, sur tuiles, tableaux et graphiques | partiel | `tests/test_a_number_is_written_one_way.py::test_the_hand_made_forms_only_become_fewer` ✅ | Few p.74 | R260 : formats.num/eur/pct (FR et EN), fmt_eur y délègue, 46 sites migrés ; restent 26 séparateurs faits main et 77 formats {:,} sous cliquet → R278 |
| REQ-FORMAT-02 | Une date affichée suit la langue du lecteur | conforme | `tests/test_a_date_shown_to_a_reader_follows_their_language.py::test_no_view_formats_a_date_day_first` ✅ | — | — |
| REQ-FORMAT-03 | Les tableaux partagent un style et des formats de colonnes | partiel | `tests/test_a_number_is_written_one_way.py::test_the_hand_made_forms_only_become_fewer` ✅ | Few p.74 | R260 : formats.table ; 45 tableaux sur 58 encore sans format, sous cliquet → R278 |

## Pages, navigation et premier écran (`pages-ux`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-UX-01 | Chaque graphique répond à une question et écrit la décision qu'il permet ; un plafond de figures au premier écran | partiel | `tests/test_the_first_screen_counts_its_gauges.py::test_no_view_exceeds_its_recorded_ceiling` ✅ | Few p.26 (l'essentiel, d'un coup d'œil) | la décision écrite n'est gardée que pour les fiches traitées par R247 ; aucun test ne l'exige partout → R271 |
| REQ-UX-02 | Naviguer dans l'app n'ouvre jamais d'onglet ; une redirection mène toujours à la même étape quel que soit l'onglet d'origine | partiel | `tests/test_navigation_inside_the_app_opens_no_tab.py::test_no_markdown_link_navigates_between_screens` ✅ | — | pas de contrat de routage unique (page d'arrivée selon l'état de configuration) testé de bout en bout → R261 |
| REQ-UX-03 | Chaque vue se rend sans erreur sur une base réelle | conforme | `tests/test_views_render_smoke.py` ✅ | — | — |

## Inscription, mise en route et identifiants (`onboarding`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ONB-01 | Le parcours d'inscription est rejouable de bout en bout (compte → mail → connexion → assistant → identifiants → collecte) | partiel | `tests/test_canary_onboarding_walk.py` ✅ | — | le mail et les inscriptions tierces (Business Manager) ne sont pas dans la marche rejouée → R270 |
| REQ-ONB-02 | Enregistrer un identifiant rend un verdict immédiat (la plateforme répond, avec des données) et le montre | conforme | `tests/test_saving_credentials_yields_a_verdict_now.py` ✅ | — | — |

## Runtime du dashboard — latence et concurrence (`app-runtime`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-RUN-01 | Un rendu ouvre au plus son plafond de connexions et les referme sur tous les chemins | conforme | `tests/test_a_render_opens_one_connection.py::test_rendering_a_view_opens_at_most_its_ceiling` ✅ | — | — |
| REQ-RUN-02 | La latence de rendu est mesurée par page (p50/p95) et reste sous son seuil d'ADR à la charge visée | partiel | `tests/test_a_fragment_never_captures_a_connection.py` ✅ | Kleppmann p.44 (percentiles) | la mesure existe (metrics_seam) mais n'a que 1-2 points en 7 jours en prod ; un test de charge par navigateurs existe (make loadtest-concurrency, R114) mais se lance à la main, sans seuil qui échoue → R266 |
| REQ-RUN-03 | Chaque conteneur a une limite de mémoire et de CPU, et la consommation par conteneur est observée | absent | `—`  | — | — → R266 |
| REQ-RUN-04 | Des sessions concurrentes ne perdent aucun rerun | absent | `—`  | Kleppmann p.44 | R114 : 33 à 37 reruns perdus à 12-24 onglets, sur une ou deux instances ; le goulot n'est pas identifié → R266 |
| REQ-RUN-05 | Le nombre de requêtes d'un rendu ne croît pas avec le nombre de locataires (pas de N+1) | absent | `—`  | Golding p.449 | onboarding_health boucle par artiste : 106 requêtes à 6 artistes, ~900 projetées à 50 → R266 |
| REQ-RUN-06 | Le pool de connexions est dimensionné pour la concurrence visée, et ses replis directs sont surveillés | partiel | `—`  | — | pool de 8 par instance, ~4 connexions par rendu → ~2 rendus concurrents avant replis directs → R266 |

## API REST (`api`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-API-01 | L'API mesure sa latence par motif de route, sans libellés non bornés | conforme | `tests/test_the_api_measures_itself_without_unbounded_labels.py::test_the_route_label_is_the_pattern_not_the_url` ✅ | — | — |
| REQ-API-02 | La latence de l'API a un chiffre publié (p95 par route) et un seuil d'alerte | conforme | `tests/test_an_api_or_dag_failure_is_a_registered_defect.py::test_the_api_latency_has_a_measured_alert_per_route` ✅ | — | R265 : p95 par route releve (0,93 s au pire sur 7 jours), alerte a 2 s pendant 15 min → R265 |

## Multi-locataire et plans (`tenancy-plans`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-TENANT-01 | Aucune surface d'un locataire ne voit les données d'un autre ; une vue or est aveugle aux lignes d'autrui | conforme | `tests/test_a_gold_view_is_blind_to_another_tenants_rows.py::test_a_gold_view_is_blind_to_another_tenants_rows` ✅ | Golding p.449 (isolation) | — |
| REQ-TENANT-02 | L'état de la flotte (DAG, autres artistes) n'apparaît jamais sur une surface d'artiste | conforme | `tests/test_fleet_state_never_reaches_a_tenant_surface.py` ✅ | — | — |

## Cybersécurité (`security`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-SEC-01 | Aucun secret n'entre dans l'historique ; un secret indexé est refusé au commit et en CI | conforme | `tests/test_a_staged_secret_is_refused.py::test_the_detector_sees_the_defect_it_is_written_for` ✅ | Janca, Alice and Bob Learn Application Security (index p.210, user secrets) | — |
| REQ-SEC-02 | Le contrôle de sécurité nocturne est bloquant (gitleaks et audit des dépendances, API comprise) | partiel | `—`  | — | gitleaks nocturne en continue-on-error, pip-audit en || true, requirements-api.txt non audité → R267 |
| REQ-SEC-03 | Aucun fichier de secret ne voyage dans une couche d'image Docker | conforme | `tests/test_a_secret_never_rides_into_an_image_layer.py::test_every_secret_the_repo_hides_is_also_kept_out_of_the_build_context` ✅ | — | — |
| REQ-SEC-04 | Aucun geste de Claude Code ne lit un fichier .env — le refus couvre Read ET le shell (cat, grep, source) | partiel | `—`  | Janca, Alice and Bob Learn Application Security (index p.210, user secrets) | Read(./.env*) est refusé, mais guard_destructive.py n'a aucune règle .env et settings.local.json autorise cat, grep, python3 — un secret peut atterrir dans le contexte → R267 |
| REQ-SEC-05 | En production, l'API refuse de démarrer sans ses secrets (démarrage strict), au lieu d'avertir | partiel | `—`  | — | API_STRICT_BOOT n'est posé que dans docker-compose.example.yml ; sinon un simple avertissement → R267 |
| REQ-SEC-06 | Aucune dépendance ne porte une vulnérabilité ignorée par son nom sans date de fin | partiel | `—`  | — | l'avis ecdsa de python-jose est ignoré par son nom dans make audit-deps ; requirements-api.txt n'est pas audité → R267 |

## Tests locaux et CI (`tests-ci`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-TEST-01 | La CI répartit la suite en shards équilibrés par des durées réelles, chaque test neuf apporte sa durée | conforme | `tests/test_a_new_test_brings_its_duration.py::test_the_hook_judges_every_tracked_test_not_only_the_staged_files` ✅ | Khorikov, Unit Testing p.113 (retour rapide) | — |
| REQ-TEST-02 | La boucle de code ne lance que les tests atteignables depuis le diff | conforme | `tests/test_the_selector_selects_what_changed.py` ✅ | — | — |
| REQ-TEST-03 | Le temps de suite publié est UNE mesure écrite par la suite elle-même | conforme | `tests/test_a_delivery_closes_on_a_green_ci.py::test_the_suite_time_is_read_from_the_run_not_written_by_hand` ✅ | — | R268 : make test écrit .claude/dev-docs/test-suite-timing.json ; le Makefile et CLAUDE.md y renvoient (le « 180 s » recopié avait deux jours de retard, 372 s mesurés) |
| REQ-TEST-04 | Un corps de fonction n'est écrit qu'une fois, dans un script ou entre scripts ; le graphe de code ne garde aucun fichier disparu | conforme | `tests/test_a_function_is_written_once.py::test_the_copies_only_become_fewer` ✅ | — | R269 : 5 groupes / 11 sites mesurés le 2026-09-27, 4 factorisés ; reste la paire de rappels d'échec DAG (R265 les factorise avec les dix autres). graphify : 2 fichiers fantômes retirés, `make graph-update` élague |

## Configuration Claude Code et poste WSL (`claude-wsl`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-CLAUDE-01 | Un agent n'existe que s'il a un déclencheur qui peut se produire ; la liste de refus des permissions ne rétrécit pas | conforme | `tests/test_claude_config_floor.py::test_the_permission_deny_list_does_not_shrink` ✅ | — | — |
| REQ-CLAUDE-02 | Claude Code lit la fiche d'un domaine avant d'y toucher ; toute exigence nouvelle entre au catalogue avec sa preuve | conforme | `tests/test_every_requirement_has_a_probe.py` ✅ | — | — |
| REQ-CLAUDE-03 | CLAUDE.md reste sous un budget de taille et ne porte que des règles vivantes | conforme | `tests/test_a_delivery_closes_on_a_green_ci.py::test_claude_md_stays_under_its_budget_not_vacuous` ✅ | — | R268 : budget 52 933 octets, ne peut que baisser (il a attrapé la propre ligne de R268) |

## Gouvernance de la roadmap (`roadmap-gov`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ROAD-01 | Toute action de code a sa ligne de roadmap AVANT, archivée seulement livrée et testée | conforme | `tests/test_an_action_is_on_the_roadmap_before_it_runs.py::test_the_detector_sees_the_defect_it_is_written_for` ✅ | — | — |
| REQ-ROAD-02 | Chaque avis du propriétaire devient une action reliée à une ligne réelle de la roadmap | conforme | `tests/test_every_dossier_action_is_in_the_roadmap.py::test_every_dossier_action_names_a_real_roadmap_row` ✅ | — | — |
| REQ-ROAD-03 | La discipline de roadmap est mesurée et son relevé n'est jamais périmé ; une livraison se ferme sur une CI verte | conforme | `tests/test_a_delivery_closes_on_a_green_ci.py::test_a_red_or_running_ci_refuses_the_closure` ✅ | — | R268 : make roadmap-close lit la CI du commit de livraison (refuse rouge, en cours, non poussé), réécrit le relevé de discipline et passe les notes du propriétaire « livré » |
| REQ-ROAD-04 | Une modification de code se rattache à LA ligne qu'elle cite, pas seulement à une ligne ouverte quelconque | conforme | `tests/test_a_commit_stays_in_its_rows_scope.py::test_a_file_outside_the_declared_scope_is_refused` ✅ | — | R268 : une ligne déclare `<!-- scope: … -->`, le hook de commit refuse un fichier produit hors de ce périmètre ; toute ligne à partir de R279 doit le déclarer |

## Classes d'erreur et registre applicatif (`error-classes`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ERR-01 | Une classe d'erreur n'entre qu'avec un billet d'admission chiffré, une signature vue rouge et un balayage | conforme | `tests/test_every_error_class_is_complete.py::test_a_class_says_how_it_is_detected` ✅ | Beyer et al., The Site Reliability Workbook p.213 (actions préventives d'un postmortem) | — |
| REQ-ERR-02 | Le registre des erreurs applicatives reçoit les erreurs de TOUTE l'infra (dashboard, API, DAG, collecteurs), par empreinte et par page | conforme | `tests/test_an_api_or_dag_failure_is_a_registered_defect.py::test_an_unhandled_api_exception_is_registered_and_stays_a_bare_500` ✅ | — | R265 : API (gestionnaire d exception, hors boucle d evenements) et 13 DAG (un seul rappel) ecrivent dans app_error_log → R265 |
| REQ-ERR-03 | Des classes GÉNÉRIQUES (par famille) précèdent les classes distinctes ; une nouvelle erreur entre comme instance d'une famille | partiel | `tests/test_the_error_class_families_only_improve.py` ✅ | — | 12 familles et 18 règles existent ; pas de table en base pour suivre pertinence et échecs des classes dans le temps → R264 |
| REQ-ERR-04 | Le balayage de toutes les signatures tient dans le budget de la CI | absent | `—`  | — | audit_runner --deterministic dépasse 1 800 s → R264 |

## Infrastructure et observabilité (`infra-observability`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-OBS-01 | Grafana montre la santé et l'échelle : CPU, RAM, disque du VPS, pool de connexions, utilisateurs connectés, latence, erreurs par page, lignes et taille de base — chacun avec un seuil d'alerte | conforme | `tests/test_a_mute_defect_gauge_does_not_read_as_zero.py::test_the_base_size_and_its_largest_tables_are_exposed` ✅ | Golding p.339 (mesurer la réponse du système); Beyer et al., SRE Workbook p.111 (alerter sur SLO) | R265 : taille de base et lignes par table exposees, panneau Base, trois regles calibrees sur 7 jours de prod → R265 |
| REQ-OBS-02 | Ce qui se trace dans Grafana n'est pas redit dans la vue admin (et inversement) | conforme | `test -f .claude/dev-docs/grafana-correspondence.md` ✅ | — | R265 (critic e) : la correspondance a conclu que l admin ne porte que du par-locataire, que Grafana ne peut pas tenir ; rien a retirer → R265 |

## Trous — exigences sans preuve rejouable

- REQ-ORCH-01
- REQ-ORCH-03
- REQ-RUN-03
- REQ-SEC-02
- REQ-SEC-04
- REQ-SEC-05
- REQ-SEC-06
- REQ-RUN-04
- REQ-RUN-05
- REQ-RUN-06
- REQ-ERR-04

## Rejouer une preuve sur une ligne précise

1. Lancer la preuve seule : `.venv/bin/python -m pytest <node> -q` ou la commande.
2. Appliquer la `mutation` déclarée de l'exigence sur SA ligne (ou `python3 tools/dev/mutate_guards.py <test>`).
3. La preuve doit ROUGIR ; restaurer, vérifier `git status` propre.
