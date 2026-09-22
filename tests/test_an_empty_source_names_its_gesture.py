"""Une source vide nomme ce qui manque, et mène quelque part.

Type: Guard
Uses: src.dashboard.utils.kpi_helpers, src.database.stripe_schema, tests.nav_source
Persists in: nothing

Le trou, mesuré le 2026-09-22
------------------------------
Une source sans donnée affichait « — » et s'arrêtait. Sur les six locataires bêta de
production, **quatre** n'avaient rien nulle part : leur accueil était un écran de
tirets, sans une seule indication de quoi faire.

Et le dépôt savait quoi dire. **Neuf messages** nommaient une page en toutes lettres,
dans une chaîne française codée en dur, sans clé de route ni bouton. Neuf fois le même
geste recopié, neuf culs-de-sac.

Les trois propriétés gardées ici
---------------------------------
1. **Chaque source porte son geste** — `valeur`, `geste`, `page`.
2. **`page` est une ROUTE VIVANTE**, pas une prose. Une page nommée en français dans
   un message ne mène nulle part ; une clé de route qui n'existe plus mène à une
   erreur. Les deux se lisent pareil dans le code, et seule la seconde peut être
   vérifiée — c'est pourquoi le registre porte des clés.
3. **Le geste ne parle jamais de plomberie.** Les raisons brutes vivent dans
   `etl_run_log.error_message` et se lisent « no SoundCloud user_id and no claimed
   track ». Les recopier sur l'écran d'un artiste est le défaut que ce dépôt a
   mesuré : 14 messages nommaient un DAG, et six disaient de lancer
   `ml_scoring_daily`, que personne ne peut lancer. Yifrah, *Microcopy* p.138 :
   « n'écris jamais à tes utilisateurs à propos du système. »

Et une quatrième, héritée : **un geste ne mène jamais à un mur de paiement.** C'est la
règle des étapes de mise en route (`test_a_declared_step_is_visible_everywhere_and_
never_locked`), transposée. Proposer « branche SoundCloud » et ouvrir une page
d'abonnement serait pire que de ne rien proposer.
"""
from __future__ import annotations

import re

import pytest

from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG
from src.database.stripe_schema import page_is_locked

_SOURCES = {s["label"]: s for s in SOURCES_CONFIG}

#: Le vocabulaire de la PLOMBERIE — ce qu'un artiste ne doit jamais lire.
#:
#: ⚠️ Chaque entrée vient d'un vrai message. `user_id`, `channel_id` et `declared`
#: sortent mot pour mot des raisons de `etl_run_log` ; `DAG` et `pipeline` du défaut
#: des 14 messages ; `artist_id` et `table` de ce qu'on écrit sans y penser.
_PLOMBERIE = (
    "dag", "pipeline", "artist_id", "user_id", "channel_id", "account_id",
    "ig_user_id", "spotify_artist_id", "declared", "collected_at", "upsert",
    "airflow", "cron", "etl", "postgres", "requête", "query", "table",
)


def test_the_registry_is_worth_checking() -> None:
    """NON-VACUITÉ. Un registre vidé rendrait zéro paramètre à tout ce qui suit."""
    assert len(SOURCES_CONFIG) >= 8, (
        f"seulement {len(SOURCES_CONFIG)} source(s) — les tests paramétrés "
        "ci-dessous ne vérifieraient presque rien.")


@pytest.mark.parametrize("label", sorted(_SOURCES))
def test_every_source_carries_what_to_do_about_it(label: str) -> None:
    """`valeur` (ce qu'on perd) et `geste` (ce qu'il y a à faire), non vides."""
    src = _SOURCES[label]
    for champ in ("valeur", "geste"):
        assert champ in src, (
            f"« {label} » ne porte pas de `{champ}` : sa tuile vide affichera un "
            "tiret et rien d'autre, comme avant le 2026-09-22.")
        rendu = src[champ]() if callable(src[champ]) else src[champ]
        assert rendu and rendu.strip(), (
            f"le `{champ}` de « {label} » est vide.")


@pytest.mark.parametrize("label", sorted(_SOURCES))
def test_every_source_points_at_a_live_route(label: str) -> None:
    """`page` est une clé de route que la navigation connaît VRAIMENT.

    Pas une prose, pas une route morte. Le bouton d'absence appelle
    `goto(source["page"])` : une clé inconnue y mène à une page qui ne se rend pas.

    ⚠️ ATTEIGNABLE, pas « au menu » — et le premier jet de ce garde a fait l'erreur.
    Il interrogeait `menu_pages()` et rougissait sur `upload_csv`, qui n'a pas
    d'entrée de menu mais dont la route vit : c'est là que l'assistant de mise en
    route envoie déposer un CSV. Le prédicat cherchait une FORME (« y a-t-il une
    entrée de menu ? ») là où la propriété est « la page se rend-elle ? ».

    Ce dépôt a déjà fait cette erreur exacte, sur `data_wrapped` le 2026-09-21, et
    en a tiré `_routable_pages()`. On le réutilise plutôt que d'en écrire un
    deuxième qui divergerait.
    """
    from tests.test_the_plan_pitch_matches_the_gate import _routable_pages

    page = _SOURCES[label].get("page")
    assert page, f"« {label} » ne porte pas de `page` : son bouton ne mène nulle part."
    assert page in _routable_pages(), (
        f"« {label} » pointe vers « {page} », qu'aucune route ne rend. Le bouton "
        f"d'absence appellerait `goto({page!r})` et la page resterait blanche. "
        f"Routes vivantes : {sorted(_routable_pages())}")


@pytest.mark.parametrize("label", sorted(_SOURCES))
def test_a_gesture_never_leads_to_a_paywall(label: str) -> None:
    """Proposer un geste et ouvrir un mur de paiement est pire que ne rien proposer.

    Transposition littérale de la règle des étapes de mise en route, qui existe
    parce qu'une étape a un jour pointé vers une page Premium.
    """
    page = _SOURCES[label]["page"]
    assert not page_is_locked("free", page), (
        f"le geste de « {label} » mène à « {page} », fermée au plan gratuit. Un "
        "artiste gratuit se verrait proposer de brancher une source et tomberait sur "
        "une page d'abonnement.")


@pytest.mark.parametrize("label", sorted(_SOURCES))
def test_a_gesture_speaks_to_a_human_not_to_the_machine(label: str) -> None:
    """LE garde qui compte. Aucun mot de plomberie dans ce qu'un artiste lit.

    ⚠️ Le prédicat cherche des mots ENTIERS. Sans ça, « etl » matcherait
    « immatriculation » et « table » matcherait « comptable » : un garde qui rougit
    sur un faux positif finit désactivé, ce qui le rend pire qu'absent.
    """
    src = _SOURCES[label]
    for champ in ("valeur", "geste"):
        rendu = (src[champ]() if callable(src[champ]) else src[champ]).lower()
        trouves = [m for m in _PLOMBERIE
                   if re.search(rf"\b{re.escape(m)}\b", rendu)]
        assert not trouves, (
            f"le `{champ}` de « {label} » parle de plomberie — {trouves} : «{rendu}». "
            "Les raisons brutes d'`etl_run_log` se TRADUISENT, elles ne se recopient "
            "pas. Ce dépôt a mesuré 14 messages artiste qui nommaient un DAG.")


def test_the_plumbing_words_would_actually_be_caught() -> None:
    """NON-VACUITÉ du test ci-dessus, et sur sa forme exacte.

    Un prédicat qui ne matche rien laisse tout passer. On lui présente donc la
    raison brute que la production émet vraiment, et on exige qu'il la refuse.
    """
    reelle = "no SoundCloud user_id and no claimed track"
    trouves = [m for m in _PLOMBERIE
               if re.search(rf"\b{re.escape(m)}\b", reelle.lower())]
    assert trouves, (
        "le détecteur de plomberie ne reconnaît pas « no SoundCloud user_id and no "
        "claimed track », qui est la raison EXACTE que `etl_run_log` porte en "
        "production pour GRiNCH et artiste1. Il ne garde donc rien.")


def test_a_common_word_is_not_a_false_positive() -> None:
    """La RÉCIPROQUE : le détecteur ne doit pas rougir sur du français ordinaire.

    « comptable » contient `table`, « immatriculation » contient `etl`. Un garde qui
    crie sur une phrase correcte finit contourné.
    """
    innocente = "ton relevé comptable et ton immatriculation"
    trouves = [m for m in _PLOMBERIE
               if re.search(rf"\b{re.escape(m)}\b", innocente.lower())]
    assert not trouves, (
        f"le détecteur voit {trouves} dans « {innocente} » — il matche des fragments "
        "de mots au lieu de mots entiers, et rougira sur des phrases correctes.")
