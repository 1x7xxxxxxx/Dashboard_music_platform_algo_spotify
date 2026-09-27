# Benchmark d'architecture — actuel contre théorique

> **Généré** par `make arch-benchmark` depuis `domains.yaml` et `requirements.yaml`.
> Ne pas éditer à la main : corriger le catalogue, puis régénérer.

**52 exigences** sur **20 domaines** (carte : 24). conforme : 27 · partiel : 19 · absent : 6 · non-mesure : 0 · RÉGRESSION : 0 · sans preuve rejouable : 8

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
| REQ-SILVER-01 | La couche argent a une identité mécanique — on sait, par le nom ou un registre, quelle vue est argent et laquelle est or | absent | `—`  | — | argent et or partagent le préfixe v_* ; aucun test ni document ne les distingue → R258 |

## Or — une définition par KPI (`gold`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-GOLD-01 | Une métrique = une définition canonique = une vue or, déclarée au registre avec son sens (flux, cumul, niveau) | conforme | `tests/test_every_metric_is_registered.py::test_every_read_gold_object_is_registered_and_no_entry_is_dead` ✅ | Reis & Housley, Fundamentals of Data Engineering p.482 (metrics layer) | — |
| REQ-GOLD-02 | Chaque KPI porte définition, source(s), formule, granularité, période et tests de qualité | partiel | `tests/test_every_metric_is_registered.py::test_every_metric_says_its_sense` ✅ | Reis & Housley p.482 | le registre porte le sens et la vue, pas encore formule, granularité, période ni le test de qualité associé → R258 |
| REQ-GOLD-03 | Un graphique ou une tuile ne lit que l'or ; le nombre de lectures du brut ne fait que baisser | partiel | `tests/test_the_bronze_boundary_only_tightens.py::test_the_bronze_boundary_never_loosens` ✅ | — | 18/64 figures et 44/162 tuiles lisent encore du brut (plafond de paires 66) — gold-coverage.md → R258 |
| REQ-GOLD-04 | Deux définitions censées coïncider sont comparées sur les vraies données, et l'écart alerte | conforme | `tests/test_the_gold_layer_agrees_with_itself.py::test_every_gold_invariant_holds_on_the_real_data` ✅ | Moses et al., Data Quality Fundamentals p.152 (piliers de l'observabilité) | — |
| REQ-GOLD-05 | Ce que la figure DESSINE est contrôlé après sa lecture or (taux ≤ 100 %, cumul qui ne retombe pas, pas deux barres sous un nom) | conforme | `tests/test_a_chart_number_is_checked_after_its_gold_read.py::test_the_detector_sees_the_defect_it_is_written_for` ✅ | — | — |

## Qualité et observabilité des données (`data-quality`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-DQ-01 | Sept familles de contrôles automatiques : doublons, valeurs impossibles, ruptures temporelles, variations anormales, divergences entre plateformes, mapping, données manquantes | partiel | `tests/test_every_quality_check_has_a_category.py` ✅ | Moses et al. p.135 et p.152 | R230 range 14 contrôles sous les 7 familles (tools/dev/dq_catalogue.py) ; manques déclarés : borne par nature de mesure, campagne sans titre, pas de scan de doublons (UNIQUE sur 119/131 tables) → R230 |
| REQ-DQ-02 | Une anomalie d'ingestion se mesure en lignes attendues × locataires contre lignes reçues, avec seuil | conforme | `tests/test_an_ingestion_gap_is_expected_against_received.py` ✅ | — | — |
| REQ-DQ-03 | Un défaut de donnée est corrigé à sa cause, pas maquillé ; une absence n'est jamais dessinée comme un zéro | conforme | `tests/test_a_figure_never_draws_a_zero_it_did_not_measure.py` ✅ | — | — → R206 |

## Filtres modulaires (`filters`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-FILTER-01 | Une seule couche de filtres (période, titre, plateforme, compte, campagne) ; aucune vue n'écrit son propre filtre | partiel | `tests/test_a_view_filters_through_the_shared_layer.py::test_no_view_writes_its_own_period_filter` ✅ | — | 7 vues passent par filters.py ; smart_date_range (imusician, meta_creatives) et meta_accounts (5 vues Meta) la contournent → R259 |
| REQ-FILTER-02 | Le filtre de période s'ouvre par défaut sur « depuis la dernière sortie », dans toute l'app | partiel | `—`  | — | chaque vue de plateforme passe last_release elle-même, mais le défaut de la couche partagée reste « current » (src/dashboard/utils/period_filter.py _default_preset) et aucun test ne l'exige → R259 |
| REQ-FILTER-03 | Élargir n'importe quel filtre ne fait jamais planter la vue | conforme | `tests/test_a_widened_filter_still_renders.py::test_widening_every_filter_does_not_raise` ✅ | — | — |

## Porte de dessin — légendes, palette, Pareto (`chart-door`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-CHART-01 | Tout graphique passe par une seule porte (légende, glossaire, palette) | conforme | `tests/test_every_chart_goes_through_the_door.py::test_no_chart_walks_around_the_door` ✅ | Few, Information Dashboard Design p.74 (attributs visuels constants) | — |
| REQ-CHART-02 | Une plateforme a UNE couleur dans toute l'app (Meta bleu, Spotify vert, SoundCloud orange…) ; aucune couleur de plateforme en dur dans les vues | partiel | `tests/test_a_platform_colour_has_one_definition.py::test_no_new_hardcoded_platform_colour` ✅ | Few p.74 | le cliquet tolère encore 42 couleurs de plateforme en dur (_PLAFOND = 42) ; les graphiques PDF (matplotlib) ont leur palette propre → R260 |
| REQ-CHART-03 | Tri Pareto par défaut sur les barres par catégorie | partiel | `tests/test_every_chart_goes_through_the_door.py` ✅ | — | Pareto opt-in, 3 appelants seulement → R260 |
| REQ-CHART-04 | Aucune redondance — une page ne dessine pas deux fois la même mesure | partiel | `tests/test_no_two_figures_on_a_page_share_a_fingerprint.py::test_no_page_draws_the_same_measure_twice` ✅ | — | une tuile qui répète un graphique de la même page n'est pas vue ; le tableau KPI → fiches n'est lu par aucun test → R258 |

## Formats — tuiles, tableaux, nombres, dates (`formats`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-FORMAT-01 | Un formateur unique pour nombres, monnaie, pourcentages et dates, sur tuiles, tableaux et graphiques | absent | `—`  | Few p.74 | 164 st.metric sans formateur commun, 12 formateurs concurrents, ~86 bricolages de séparateur → R260 |
| REQ-FORMAT-02 | Une date affichée suit la langue du lecteur | conforme | `tests/test_a_date_shown_to_a_reader_follows_their_language.py::test_no_view_formats_a_date_day_first` ✅ | — | — |

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

## API REST (`api`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-API-01 | L'API mesure sa latence par motif de route, sans libellés non bornés | conforme | `tests/test_the_api_measures_itself_without_unbounded_labels.py::test_the_route_label_is_the_pattern_not_the_url` ✅ | — | — |

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

## Tests locaux et CI (`tests-ci`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-TEST-01 | La CI répartit la suite en shards équilibrés par des durées réelles, chaque test neuf apporte sa durée | conforme | `tests/test_a_new_test_brings_its_duration.py::test_the_hook_judges_every_tracked_test_not_only_the_staged_files` ✅ | Khorikov, Unit Testing p.113 (retour rapide) | — |
| REQ-TEST-02 | La boucle de code ne lance que les tests atteignables depuis le diff | conforme | `tests/test_the_selector_selects_what_changed.py` ✅ | — | — |
| REQ-TEST-03 | Les chiffres de temps de suite publiés sont UNE source générée, pas trois documents qui se contredisent | absent | `—`  | — | — → R268 |

## Configuration Claude Code et poste WSL (`claude-wsl`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-CLAUDE-01 | Un agent n'existe que s'il a un déclencheur qui peut se produire ; la liste de refus des permissions ne rétrécit pas | conforme | `tests/test_claude_config_floor.py::test_the_permission_deny_list_does_not_shrink` ✅ | — | — |
| REQ-CLAUDE-02 | Claude Code lit la fiche d'un domaine avant d'y toucher ; toute exigence nouvelle entre au catalogue avec sa preuve | partiel | `tests/test_every_requirement_has_a_probe.py` ✅ | — | la règle CLAUDE.md et l'injection par mots-clés sont livrées par R257 → R257 |

## Gouvernance de la roadmap (`roadmap-gov`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ROAD-01 | Toute action de code a sa ligne de roadmap AVANT, archivée seulement livrée et testée | conforme | `tests/test_an_action_is_on_the_roadmap_before_it_runs.py::test_the_detector_sees_the_defect_it_is_written_for` ✅ | — | — |
| REQ-ROAD-02 | Chaque avis du propriétaire devient une action reliée à une ligne réelle de la roadmap | conforme | `tests/test_every_dossier_action_is_in_the_roadmap.py::test_every_dossier_action_names_a_real_roadmap_row` ✅ | — | — |
| REQ-ROAD-03 | La discipline de roadmap est mesurée et son relevé n'est jamais périmé | partiel | `make roadmap-discipline` ✅ | — | .claude/dev-docs/roadmap-discipline.json date du 2026-09-26 et liste des lignes fermées depuis → R268 |

## Classes d'erreur et registre applicatif (`error-classes`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-ERR-01 | Une classe d'erreur n'entre qu'avec un billet d'admission chiffré, une signature vue rouge et un balayage | conforme | `tests/test_every_error_class_is_complete.py::test_a_class_says_how_it_is_detected` ✅ | Beyer et al., The Site Reliability Workbook p.213 (actions préventives d'un postmortem) | — |
| REQ-ERR-02 | Le registre des erreurs applicatives reçoit les erreurs de TOUTE l'infra (dashboard, API, DAG, collecteurs), par empreinte et par page | partiel | `tests/test_an_error_leaves_a_row.py` ✅ | — | app_error_log n'est alimenté que par le dashboard ; l'API et les DAG ne l'appellent pas ; « No data » sur les erreurs par page dans Grafana → R265 |
| REQ-ERR-03 | Des classes GÉNÉRIQUES (par famille) précèdent les classes distinctes ; une nouvelle erreur entre comme instance d'une famille | partiel | `tests/test_the_error_class_families_only_improve.py` ✅ | — | 12 familles et 18 règles existent ; pas de table en base pour suivre pertinence et échecs des classes dans le temps → R264 |

## Infrastructure et observabilité (`infra-observability`)

| id | exigence | verdict | preuve | théorie | écart / livrable |
|---|---|---|---|---|---|
| REQ-OBS-01 | Grafana montre la santé et l'échelle : CPU, RAM, disque du VPS, pool de connexions, utilisateurs connectés, latence, erreurs par page, lignes et taille de base — chacun avec un seuil d'alerte | partiel | `python3 -c "import yaml;yaml.safe_load(open('deploy/prometheus/rules/streamlytics.yml'))"` ✅ | Golding p.339 (mesurer la réponse du système); Beyer et al., SRE Workbook p.111 (alerter sur SLO) | taille base, lignes, ressources par conteneur et quotas ne sont pas des métriques (make scale-check relit les déclencheurs d'ADR-014 à la main) ; erreurs par page sans données → R265 |
| REQ-OBS-02 | Ce qui se trace dans Grafana n'est pas redit dans la vue admin (et inversement) | partiel | `test -f .claude/dev-docs/grafana-correspondence.md` ✅ | — | la correspondance est un document, pas un contrôle → R265 |

## Trous — exigences sans preuve rejouable

- REQ-SILVER-01
- REQ-ORCH-01
- REQ-ORCH-03
- REQ-FILTER-02
- REQ-FORMAT-01
- REQ-RUN-03
- REQ-SEC-02
- REQ-TEST-03

## Rejouer une preuve sur une ligne précise

1. Lancer la preuve seule : `.venv/bin/python -m pytest <node> -q` ou la commande.
2. Appliquer la `mutation` déclarée de l'exigence sur SA ligne (ou `python3 tools/dev/mutate_guards.py <test>`).
3. La preuve doit ROUGIR ; restaurer, vérifier `git status` propre.
