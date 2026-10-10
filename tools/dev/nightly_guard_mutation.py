#!/usr/bin/env python3
"""Mutate, every night, the guards changed this week — and name the ones nothing turns red.

Type: Utility
Uses: tools/dev/mutate_guards.py (try_mutations), git log
Triggers: .github/workflows/security-nightly.yml, job `guard-mutation`
Persists in: .claude/dev-docs/guard-red-log.jsonl (gitignored, append-only) — one dated
             line per guard the job saw go red, naming the mutation; uploaded as the
             `guard-red-log` CI artifact, merged locally by `--fetch`. Prints a verdict per
             guard, exit 1 when a NEW guard is suspect.

Rule 15ter says « mutate a new guard before believing it », and until 2026-09-26 that was a
gesture done by hand. The same day, doing it by hand for ~30 guards found three real defects
in guards (one crashed instead of judging, one proof pointed at a renamed test, two
mutations stayed green without embodying the defect). A gesture that finds that much is a
machine's job.

What it can say, honestly: a guard that stays GREEN on every mutation it was given is a
guard nobody has seen bite — it is flagged. What it cannot say: that a RED mutation embodies
the class (a renamed identifier often breaks a guard for a trivial reason). So red is never
reported as proof; only the absence of any red is reported, as a suspicion to read.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutate_guards as mg  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_MAX_GUARDS = 12          # each guard costs up to 7 pytest runs; the nightly is not unbounded
_SELF_PROVING_PER_NIGHT = 4   # catalogue self-proving guards with no dated red, per night
RED_LOG = _ROOT / ".claude/dev-docs/guard-red-log.jsonl"
_CATALOGUE = _ROOT / ".claude/dev-docs/error-classes.md"
_CLAIM = re.compile(r"^- seen_red:\s*self-proving \((tests/[\w./-]+\.py)", re.M)


def changed_guards(days: int = 2) -> list[str]:
    """Guard files ADDED in the window — rule 15ter is about NEW guards (168 were merely
    modified in the week of 2026-09-26: mutating all of them is a day, not a night)."""
    out = subprocess.run(["git", "-C", str(_ROOT), "log", f"--since={days}.days", "--diff-filter=A", "--name-only",
                          "--format=", "--", "tests/test_*.py"],
                         capture_output=True, text=True).stdout.split()
    seen, keep = set(), []
    for rel in out:
        if rel not in seen and (_ROOT / rel).is_file():
            seen.add(rel)
            keep.append(rel)
    return keep


# R238 (2026-09-27) — two kinds of evidence the generic mutations cannot produce, and
# that made the job mail « 6 gardes à relire » for six guards that all bite.
#
# 1. A guard that PROVES ITSELF: a test that builds the defect and demands the detector
#    see it (`test_the_detector_sees_…`) turns red at every run, not one night in six.
# 2. A red seen BY HAND on a mutation that EMBODIES the defect — the only red that says
#    something about the class (a generic rename breaks a guard for a trivial reason).
#    Written with the mutation, never a bare « ok »: a human decided it embodies the class.
SEEN_RED: dict[str, str] = {
    "tests/test_a_push_carries_the_tree_seen_green.py":
        "2026-10-08 — R467 : `verdict` ne compte plus les fichiers changés depuis le run vert "
        "(le push du 2026-10-07, R444) → 2 rouges",
    "tests/test_the_onboarding_matrix_is_dense.py":
        "2026-10-08 — R467 : la case compacte reprend 34px (la matrice qui poussait le bouton "
        "sous la ligne de flottaison, R439) → 2 rouges",
    "tests/test_a_committed_change_is_still_selected.py":
        "2026-10-08 — R467 : `_unpushed_base` rend « HEAD » (le défaut R464) → 1 rouge",
    "tests/test_the_welcome_offer_is_two_highlighted_plans.py":
        "2026-10-08 — R467 : PLAN_HIGHLIGHT premium « violet » → « blue », une seule couleur "
        "pour deux plans → 1 rouge",
    "tests/test_every_navigation_button_reaches_its_page.py":
        "2026-10-08 — R467 : plan_gate `goto(page_key)` → `goto(\"upgrade\")` (le défaut "
        "R454, renvoi à l'accueil) → 1 rouge",
    "tests/test_a_ci_red_says_how_it_escaped.py":
        "2026-10-08 — R467 : `escape` rend « local-vs-ci » sans regarder la porte de push "
        "(deux routes confondues) → 1 rouge",
    "tests/test_service_is_frozen.py":
        "2026-10-07 — R434 : ligne « Déclenchement des algos Spotify » font-size 1.9rem "
        "→ 1.2rem → 3 rouges (photos with_link, no_link, mail_open)",
    "tests/test_service_request_mail.py":
        "2026-10-06 — R430 : Reply-To posé brut (sans parseaddr/_one_line) → rouge "
        "(en-tête Bcc injecté refusé à la sérialisation)",
    "tests/test_pdf_report_is_frozen.py":
        "2026-10-06 — R428 : titre de la vue « 📄 Rapport PDF » → « 📄 Rapport PDFx » "
        "→ 2 rouges (photo premium + gratuit)",
    "tests/test_home_periodic_axis_is_log.py":
        "2026-10-06 — R427 : axe `type=\"log\"` → `\"linear\"` en non cumulé → 1 rouge",
    "tests/test_home_is_frozen.py":
        "2026-10-06 — R427 : axe `type=\"log\"` → `\"linear\"` → 1 rouge "
        "(photo full_not_cumulative) ; `log_periodic=False` à l'appel de l'Accueil → rouge",
    "tests/test_home_gate_28d_gap.py":
        "2026-10-06 — R426 : RR_WINDOW_DAYS 28 → 35 → 1 rouge (fenêtre Release Radar)",
    "tests/test_the_admin_screen_says_what_the_mail_says.py":
        "2026-10-06 — R422 : readiness_snapshot sans les verdicts rejoués (`probes=` retiré) "
        "→ 1 rouge (« the screen must replay the verdict ») ; collection_failures gardant "
        "les `success` → 1 rouge (l'écran et le mail divergent du ledger)",
    "make schema-check-local":
        "2026-10-05 — R412 : trg_revision_s4a_song_timeline commenté dans la migration 096 "
        "→ exit 2, « a trigger present on one side only » (REQ-BRONZE-02)",
    "tests/test_a_creative_funnel_never_widens.py":
        "2026-09-27 — funnel_stages lit `total_results` (le résultat de l'objectif) comme "
        "clics sortants → 3 rouges",
    "tests/test_a_roi_verdict_needs_a_crossing_and_enough_points.py":
        "2026-09-27 — MIN_FIT_POINTS 5 → 2 (un ajustement sur deux points) → 2 rouges ; "
        "2026-10-05 — R412 : MIN_FIT_POINTS 5 → 2 rejoué → 2 rouges",
    "tests/test_a_floor_probability_is_never_shown_as_a_measure.py":
        "2026-09-27 — proba_affichable ne refuse plus le plancher → 16 rouges ; "
        "2026-10-05 — R412 : le refus du plancher retiré de proba_affichable → 15 rouges",
    "tests/test_a_lever_curve_resolves_where_the_model_responds.py":
        "2026-09-27 — _lever_grid échantillonne un levier _log LINÉAIREMENT en unités "
        "humaines (le défaut mesuré) → 7 rouges",
    "tests/test_every_quality_check_has_a_category.py":
        "2026-09-27 — un check_ du soir ajouté sans catégorie → 1 rouge ; un pointeur "
        "renommé vers une fonction absente → 2 rouges",
    # R323 (2026-09-29): the three the 09-28 night listed « à relire », re-mutated by hand.
    "tests/test_the_fleet_readiness_does_not_grow_with_tenants.py":
        "2026-09-29 — readiness_many rendu par le chemin par locataire (artist_readiness en "
        "boucle) → 15 requêtes par locataire contre une borne de 3, 1 rouge",
    "tests/test_a_release_is_benchmarked_with_its_spend.py":
        "2026-09-29 — worth_a_panel répond True sur un cadre tout à zéro → 1 rouge ; "
        "2026-10-05 — R412 : worth_a_panel `> 0` → `>= 0` → 1 rouge",
    "tests/test_engagement_stacks_actions_not_their_total.py":
        "2026-09-29 — page_interactions remis dans _ENG_STACK (l'agrégat empilé avec ce "
        "qu'il contient) → 1 rouge",
    "tests/test_skills_rules_and_injections_are_counted.py":
        "2026-10-04 — compteur de hooks sans le test de `type` dans la condition d'échec "
        "(le run annulé non compté) → 1 rouge",
    "tests/test_the_precompact_hook_saves_the_state.py":
        "2026-10-04 — court-circuit `_same_state` retiré (second instantané identique écrit) "
        "→ 1 rouge ; 2026-10-05 — R414 : bloc night-status gardé dans la comparaison, plafond "
        "de lignes retiré, `status` → `check` → 1 rouge chacun"
        " ; 2026-10-08 — R471 : `_same_state` court-circuité (`if False and …`) → 1 rouge",
    "tests/test_every_defect_kind_can_close.py":
        "2026-10-04 — un cron clos par le rc=0 de n'importe quelle étape → 1 rouge",
    "tests/test_every_harness_component_has_a_requirement.py":
        "2026-10-04 — vérification de couverture des composants retirée → 1 rouge"
        " ; 2026-10-08 — R471 : `composants:` de pre_compact.py vidé dans requirements.yaml → 1 rouge (`return []` dans component_errors reste vert : mutation vide sur un arbre sain)",
    "tests/test_the_harness_report_renders_every_state.py":
        "2026-10-04 — branche « verte, non prouvée » retirée des opportunités → 1 rouge ; "
        "2026-10-05 — R413 : _never_invoked ignorant `manual` → 1 rouge ; "
        "2026-10-05 — R416 : différé ignoré, inventaire compté, suggestion ignorée, chemins "
        "comptés comme suggestion → 1 rouge chacun",
    "tests/test_a_governance_commit_runs_its_readers.py":
        "2026-10-04 — `|| exit 1` retiré de roadmap-close → 1 rouge ; scénario R356 rejoué → rouge",
    "tests/test_a_recurrence_ticket_can_be_answered.py":
        "2026-10-04 — `_answer` sans la date du dernier retour propre → 1 rouge ; padding CLI d'origine → 1 rouge",
    "tests/test_rex_validation_reads_only_tracked_files.py":
        "2026-10-04 — filtre `visible` retiré de `_iter_files` → 1 rouge ; `_git_visible` rendant set() hors dépôt → 1 rouge",
    "tests/test_tests_never_write_the_real_measurement_logs.py":
        "2026-10-04 — condition `session_id` retirée d'inject_context.main → 1 rouge ; `nr.JOURNAL` rétabli dans close_night_unit → 1 rouge",
    "tests/test_every_session_starts_by_reading_the_ops_mails.py":
        "2026-10-04 — hook relancé avec cwd=_ROOT → 1 rouge (marqueur absent du tmp)",
    "tests/test_the_engineering_loop_returns_a_manifest.py":
        "2026-10-04 — trouvaille DO-NOT-BUILD envoyée à Fix → 1 rouge",
    "tests/test_suggest_sweep_suggests_after_a_fix.py":
        "2026-10-04 — `if commits:` → `if False:` → 1 rouge ; mots français retirés de `_FIX_RE` → 1 rouge",
    "tests/test_a_skill_loads_when_its_subject_is_touched.py":
        "2026-10-04 — `keywords:` retiré de dashboard-view → 1 rouge ; `paths:` → `globs:` dans python.md → 1 rouge",
    "tests/test_containers_are_on_demand.py":
        "2026-10-04 — exemption élargie à AutoRemove seul → rouge ; ligne idle_containers retirée de night-status → 1 rouge",
    "tests/test_new_guards_are_mutated_every_night.py":
        "2026-10-04 — record_red écrivant aussi une mutation verte → 1 rouge ; rotation figée (`start = 0`) → 1 rouge ; "
        "2026-10-05 — re-muté après R412 : garde `source` de record_red neutralisée → 1 rouge",
    # R364 — the 42 « verte, non prouvée » proofs, mutated by hand on 2026-10-04.
    "tests/test_every_metric_is_registered.py":
        "2026-10-04 — formula de v_s4a_song_daily vidée (metric_registry.py:50) → 1 rouge ; entrée v_spotify_followers_daily commentée → 1 rouge",
    "tests/test_an_ingestion_gap_is_expected_against_received.py":
        "2026-10-04 — attendu = somme/jours non vides au lieu de /7 (db_health.py:185) → 1 rouge",
    "tests/test_a_nominal_bar_chart_is_sorted_pareto.py":
        "2026-10-04 — pareto_by_default(fig) → False dans apply_defaults (charts.py:151) → 1 rouge",
    "tests/test_the_first_screen_counts_its_gauges.py":
        "2026-10-04 — un st.metric de plus dans billing.show(), déjà à son plafond de 6 → 1 rouge ; "
        "2026-10-05 — R412 : 7 st.metric ajoutés à billing.show() → 1 rouge",
    "tests/test_saving_credentials_yields_a_verdict_now.py":
        "2026-10-04 — run_probes_now remplacé par pass à l'enregistrement (_render.py:1185) → 1 rouge",
    "tests/test_a_secret_never_rides_into_an_image_layer.py":
        "2026-10-04 — ligne `.env` retirée de .dockerignore:70 → 1 rouge",
    "tests/test_every_error_class_is_complete.py":
        "2026-10-04 — `- signature:` retirée d'une classe deterministic (error-classes.md:651) → 1 rouge",
    "tests/test_grafana_and_admin_do_not_say_the_same_thing.py":
        "2026-10-04 — panneau « Processus — RAM residente » renommé → 1 rouge ; `import psutil` dans admin.py → 1 rouge",
    "tests/test_an_api_or_dag_failure_is_a_registered_defect.py":
        "2026-10-04 — `sum by (le, route)` → `sum by (le)` (streamlytics.yml:245) → 1 rouge ; _record retiré du handler (error_capture.py:61) → 1 rouge",
    "tests/test_a_delivery_closes_on_a_green_ci.py":
        "2026-10-04 — ci_verdict rend « ok » sur failure (roadmap.py:203) → 1 rouge ; CLAUDE.md +81 octets au-dessus du budget → 1 rouge"
        " ; 2026-10-05 — R368 : « ~180 s » écrit à la main dans l'aide de make test → 1 rouge",
    "tests/test_the_guard_axis_is_measured_without_immortal_time.py":
        "2026-10-04 — la branche sans-garde verse toute l'exposition dans « avec-garde » (error_class_health.py:882) → 1 rouge",
    "tests/test_every_object_has_a_layer.py":
        "2026-10-04 — clé REGISTRY v_s4a_song_measured_span renommée (metric_registry.py:52) → 1 rouge",
    "tests/test_the_period_filter_defaults_to_the_whole_history.py":
        "2026-10-04 — default_override=\"last_release\" → None (period_filter.py:275) → 1 rouge"
        " ; 2026-10-05 — R368 : _uses_the_layer comptant un import du filtre de COMPTE → 2 vues sans période vues"
        " ; 2026-10-09 — R478 : default_override \"all\" → \"last_release\" dans span_period_filter → 1 rouge",
    "tests/test_a_number_is_written_one_way.py":
        "2026-10-04 — st.dataframe(df) brut ajouté à recap.py:37 → 1 rouge ; .style.map retiré (meta_mapping/_tracks.py:341) → 1 rouge"
        " ; 2026-10-05 — R368 : _SEPARATORS réduit à l'espace seul → 1 rouge (16 hacks à espace fine insécable)",
    "tests/test_the_tenant_loops_are_the_accepted_ones.py":
        "2026-10-05 — R367 : boucle `for artist_id` ajoutée à youtube_daily.py → 1 rouge ; cible renommée a_id (meta_ads_api_daily.py:68) → 1 rouge",
    "tests/test_the_pool_covers_the_declared_concurrency.py":
        "2026-10-05 — R367 : maxconn=4 (api/main.py:104) → 1 rouge ; maxconn=60 (dashboard/utils/__init__.py:72) → 1 rouge",
    "tests/test_views_render_smoke.py":
        "2026-10-04 — raise RuntimeError en tête de privacy.show() → 1 rouge",
    "tests/test_fleet_state_never_reaches_a_tenant_surface.py":
        "2026-10-04 — `and is_admin()` retiré avant _render_dag_status_badge (_render.py:736) → 1 rouge",
    "tests/test_an_error_class_is_generic_tracked_and_exported.py":
        "2026-10-04 — duplicate_gap rend None sans `closest:` (audit_runner.py:777) → 1 rouge ; over_budget toujours None (:271) → 1 rouge"
        " ; 2026-10-05 — R368 : sys.exit(3) retiré après over_budget dans main() → 1 rouge",
    "tests/test_api_security.py":
        "2026-10-04 — _strict() `or` → `and` (api/main.py:41) → 1 rouge",
    "tests/test_a_bash_guard_reads_the_command_not_the_prose.py":
        "2026-10-04 — filtre tête-de-segment de pkill désactivé (guard_destructive.py:392) → 1 rouge",
    "tests/test_a_platform_colour_has_one_definition.py":
        "2026-10-04 — _SPOTIFY_GREEN = \"#1DB954\" au lieu de platform_color (spotify_s4a_combined.py:74) → 1 rouge",
    "tests/test_a_date_shown_to_a_reader_follows_their_language.py":
        "2026-10-04 — strftime('%Y-%m-%d') → '%d/%m/%Y' (billing.py:327) → 1 rouge"
        " ; 2026-10-05 — R368 : 5 sites jour-mois-année courte (home_tiles ×2, meta_ads_overview ×2, _tab_model) vus par la forme élargie → 1 rouge",
    "tests/test_canary_onboarding_walk.py":
        "2026-10-04 — platform_status rend OK au lieu de NO_DATA sans données (artist_readiness.py:93) → 1 rouge",
    "tests/test_a_new_advisory_fails_the_nightly.py":
        "2026-10-04 — continue-on-error sous l'étape gitleaks (security-nightly.yml:212) → 1 rouge ; recheck-by échu (pip-audit-accepted.txt:10) → 1 rouge"
        " ; 2026-10-05 — R368 : `|| true` ajouté à la ligne pip_audit_gate du workflow → 1 rouge",
    "tests/test_a_mute_defect_gauge_does_not_read_as_zero.py":
        "2026-10-04 — yield g3 remplacé par pass (defect_gauge.py:295) → 1 rouge",
    "tests/test_the_shards_are_balanced_by_real_durations.py":
        "2026-10-04 — .test_durations vidé à {} → 1 rouge",
    "tests/test_the_bronze_boundary_only_tightens.py":
        "2026-10-04 — lecture de meta_insights_performance_day ajoutée à meta_breakdowns.show() → 1 rouge",
    "tests/test_a_figure_never_draws_a_zero_it_did_not_measure.py":
        "2026-10-04 — _continuous remplit les jours non mesurés par 0 (platform_chart.py:118) → 24 rouges",
    "tests/test_navigation_inside_the_app_opens_no_tab.py":
        "2026-10-04 — lien markdown ?page=upgrade ajouté à billing.show() → 1 rouge",
    "tests/test_a_render_opens_one_connection.py":
        "2026-10-04 — seconde get_db_connection() dans sacem.show() → 1 rouge (2 > 1)",
    "tests/test_a_new_test_brings_its_duration.py":
        "2026-10-04 — prédicat de outside() forcé à True (check_durations_are_collectable.py:116) → 1 rouge"
        " ; 2026-10-05 — R368 : main() sans outside() sur `sans` → 1 rouge (test non suivi refusé)",
    "tests/test_no_shell_gesture_reads_a_dotenv.py":
        "2026-10-04 — _reads_an_env_file rend None (guard_destructive.py:756) → 14 rouges sur test_a_read_of_a_dotenv_is_blocked",
    "tests/test_a_commit_stays_in_its_rows_scope.py":
        "2026-10-04 — out_of_scope rend [] sans condition (require_roadmap_id.py:91) → 1 rouge"
        " ; 2026-10-08 — R471 : out_of_scope rend [] sans condition (require_roadmap_id.py:139) → 1 rouge",
    "tests/test_every_command_and_skill_has_a_trigger.py":
        "2026-10-04 — /zz-ghost nommé seulement dans tooling-reference.md → 1 rouge ; `.claude/workflows/*` retiré des surfaces → 1 rouge (db-schema) ; lookbehind retiré du motif → 1 rouge",
    "tests/test_the_schema_gate_decides_correctly.py":
        "2026-10-05 — R368 : \"trg\" retiré des sortes comparées → 7 rouges ; trigger de l'historique commenté dans la migration 096 → schema-check-local rouge",
    # R400 (nuit du 2026-10-05) : cinq gardes rendus sur base live — en CI sans base ils
    # sautent, donc aucune mutation générique ne peut les y voir rougir.
    "tests/test_the_s4a_entry_page_has_no_tabs.py":
        "2026-10-05 — saisie_s4a.show() rouvre `st.tabs(['Saisie', 'Pari'])` → rouge "
        "(« the S4A entry page has tabs again »)",
    "tests/test_the_mapping_page_is_two_expanders.py":
        "2026-10-05 — meta_mapping.show() rouvre `st.tabs` → rouge (« still renders tabs »)",
    "tests/test_apple_shazams_sit_beside_the_top10.py":
        "2026-10-05 — le graphique Shazam replié dans un expander « Shazams par chanson » "
        "→ rouge (« folded in an expander again »)",
    "tests/test_the_release_budget_is_one_call.py":
        "2026-10-05 — `_release_budget_line` ne compare plus le titre du budget → rouge "
        "(« a budget priced for A shown under B »)",
    "tests/test_the_home_stops_at_the_numbers.py":
        "2026-10-05 — home.show() rappelle `render_meta_advice` → rouge "
        "(« home.py calls render_meta_advice again »)",
    "tests/test_the_login_lockout_counts_every_failure.py":
        "2026-10-05 — record_password_failure en lecture-puis-écriture (mise à jour perdue) "
        "→ rouge (« 1 comptés + 0 refusés verrouillés ≠ 8 ») ; remplacé par "
        "claim_login_attempt (R398)",
    "tests/test_a_locked_account_checks_nothing.py":
        "2026-10-05 — claim_login_attempt sans la clause `locked_until` du WHERE → rouge "
        "(« ran bcrypt 12 times ») ; le contrôle du verrou retiré de _show_totp_challenge "
        "→ rouge (« cleared the lock ») ; le `raise` du collecteur rendu en warning → rouge",
    # R493 — mailés « personne ne l'a vu mordre » deux nuits : le harnais mutait des vues
    # que ces gardes n'importent pas. Mutés à la main sur LEUR défaut, chacun rouge en
    # AssertionError (un jugement, pas un plantage).
    "tests/test_the_soundcloud_page_reads_at_a_glance.py":
        "2026-10-10 — top_figure trié `ascending=True` (soundcloud.py:439) → 1 rouge "
        "(« ['Gros','Moyen','Petit'] == ['Petit','Moyen','Gros'] »)",
    "tests/test_the_youtube_page_reads_at_a_glance.py":
        "2026-10-10 — top_figure trié `ascending=True` (youtube.py:157) → 1 rouge "
        "(« [1000, 400, 100] == [100, 400, 1000] »)",
    "tests/test_the_momentum_chart_shows_only_what_moves.py":
        "2026-10-10 — moving_songs rend `spans` sans filtre (spotify_s4a_combined.py:354) "
        "→ 2 rouges (le titre immobile montré ; plus de barres PI propres)",
}


def self_proving(path: Path) -> bool:
    """Does the guard carry a test that fabricates its defect? Read in the AST."""
    import ast
    tree = ast.parse(path.read_text())
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name.startswith("test_the_detector_sees") for n in ast.walk(tree))


# R360 (2026-10-04) — REQ-HARN-19. 407 of 429 classes say `seen_red: self-proving`: a test
# fabricates the defective INPUT and demands the detector fire. That is « seen FIRE every
# run », not « seen RED »: a detector made blind is caught only if the test also fails when
# the code it protects is mutated — and nothing recorded whether it ever did. The job now
# writes the date and the mutation each time it sees a guard go red. ⚠️ A generic mutation
# (identifier → identifier_MUTE) says « this guard bites », never « it embodies the class ».
def record_red(rel: str, result: dict, today: str, log: Path = RED_LOG) -> bool:
    """Append one dated line when `result` is a red mutation; False, nothing written, else."""
    if "source" not in result:
        return False
    log.parent.mkdir(parents=True, exist_ok=True)
    line = {"date": today, "guard": rel, "source": result["source"],
            "target": result["cible"], "line": result["ligne"], "tries": result["essais"]}
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return True


def reds_seen(log: Path = RED_LOG) -> dict[str, dict]:
    """Latest red record per guard file. A malformed line is skipped, never fatal."""
    out: dict[str, dict] = {}
    if not log.is_file():
        return out
    for raw in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ok = (isinstance(rec, dict) and rec.get("guard") and rec.get("source")
              and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(rec.get("date", ""))))
        if ok and rec["date"] >= out.get(rec["guard"], {}).get("date", ""):
            out[rec["guard"]] = rec
    return out


def self_proving_backlog(catalogue: str, seen: dict[str, dict], root: Path = _ROOT) -> list[str]:
    """Guard files the catalogue calls self-proving that no mutation has yet turned red."""
    files = dict.fromkeys(_CLAIM.findall(catalogue))
    return sorted(f for f in files if f not in seen and (root / f).is_file())


def tonight(backlog: list[str], day: date, limit: int) -> list[str]:
    """A window that ROTATES with the date. The CI runner starts with an empty log every
    night, so « the first N not yet seen » would be the same N forever there."""
    if not backlog or limit <= 0:
        return []
    start = (day.toordinal() * limit) % len(backlog)
    return (backlog[start:] + backlog[:start])[:limit]


def fetch(log: Path = RED_LOG) -> int:
    """Merge the last nightly run's `guard-red-log` artifact into the local log (needs gh)."""
    run = subprocess.run(["gh", "run", "list", "--workflow", "security-nightly.yml", "-L", "1",
                          "--json", "databaseId", "-q", ".[0].databaseId"],
                         capture_output=True, text=True, cwd=_ROOT).stdout.strip()
    if not run:
        print("❌ no security-nightly run found — run: gh auth status")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        got = subprocess.run(["gh", "run", "download", run, "-n", "guard-red-log", "-D", tmp],
                             capture_output=True, text=True, cwd=_ROOT)
        remote = Path(tmp) / log.name
        if got.returncode or not remote.is_file():
            print(f"ℹ️ run {run}: no guard-red-log artifact (no red that night)")
            return 0
        known = set(log.read_text(encoding="utf-8").splitlines()) if log.is_file() else set()
        new = [ln for ln in remote.read_text(encoding="utf-8").splitlines() if ln and ln not in known]
    if new:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write("".join(ln + "\n" for ln in new))
    print(f"✅ run {run}: {len(new)} new red record(s) merged into {log.name}")
    return 0


def verdict(result: dict) -> str | None:
    """A suspicion to report, or None. Pure: tested without running anything."""
    if "skipped" in result:
        return "rouge AVANT toute mutation — le garde ne passe pas sur l'arbre tel quel"
    if "aucune" in result and result["aucune"] > 0:
        return f"vert sur les {result['aucune']} mutation(s) essayées — personne ne l'a vu mordre"
    if "epuise" in result:
        return f"vert sur {result['epuise']} mutations, budget épuisé — personne ne l'a vu mordre"
    return None          # a red mutation, or no applicable site (nothing to conclude)


def attempts(result: dict) -> list[str]:
    """What a suspect verdict was built on — each site tried, crashes marked. Pure.

    R493 : « vert sur 6 mutations » sans les nommer ne sépare pas un garde aveugle d'un
    harnais qui mute ailleurs ; trois gardes sains ont été mailés deux nuits ainsi.
    """
    crashes = set(result.get("crashes", []))
    return [f"      · {w}" + (" — plantage, pas un jugement" if w in crashes else " — vert")
            for w in result.get("tried", [])]


def mutate_self_proving(today: str, limit: int = _SELF_PROVING_PER_NIGHT) -> int:
    """Mutate a few catalogue self-proving guards with no dated red; record each red.
    Green here is not a suspect (the fabrication may live in the test): it is only shown."""
    backlog = self_proving_backlog(_CATALOGUE.read_text(encoding="utf-8"), reds_seen())
    batch = tonight(backlog, date.fromisoformat(today), limit)
    print(f"▶ {len(batch)} garde(s) auto-prouvant(s) sans rouge daté mutés "
          f"({len(backlog)} dans le reliquat)")
    seen = 0
    for rel in batch:
        result = mg.try_mutations(_ROOT / rel)
        if record_red(rel, result, today):
            seen += 1
            print(f"   ✓ {rel} — vu rouge le {today} : {result['source']}:{result['ligne']} "
                  f"`{result['cible']}` → `{result['cible']}_MUTE`")
        else:
            print(f"   · {rel} — aucun rouge daté ({verdict(result) or 'rien à muter'})")
    return seen


def main() -> int:
    if "--fetch" in sys.argv[1:]:
        return fetch()
    limit = next((int(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--self-proving=")),
                 _SELF_PROVING_PER_NIGHT)
    today = date.today().isoformat()
    guards, credited = [], []
    for rel in changed_guards():
        if rel in SEEN_RED:
            credited.append(f"   ✓ {rel} — vu rouge à la main : {SEEN_RED[rel]}")
        elif self_proving(_ROOT / rel):
            credited.append(f"   ✓ {rel} — auto-prouvant (il fabrique son défaut à chaque run)")
        else:
            guards.append(rel)
    if credited:
        print("\n".join(credited))
    dropped = max(0, len(guards) - _MAX_GUARDS)
    guards = guards[:_MAX_GUARDS]
    print(f"▶ {len(guards)} garde(s) ajouté(s) en 2 jours (le job tourne chaque nuit)"
          + (f" — {dropped} non mutés cette nuit (plafond {_MAX_GUARDS})" if dropped else ""))
    suspects = 0
    for rel in guards:
        result = mg.try_mutations(_ROOT / rel)
        record_red(rel, result, today)
        v = verdict(result)
        suspects += v is not None
        print(f"   {'✗' if v else '✓'} {rel}" + (f" — {v}" if v else ""))
        if v:
            print("\n".join(attempts(result)))
    mutate_self_proving(today, limit)
    print(f"{'❌' if suspects else '✅'} {suspects} garde(s) à relire")
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
