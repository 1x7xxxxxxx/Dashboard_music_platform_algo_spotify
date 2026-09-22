"""Une source, une table, deux lecteurs — et aucun des deux n'en ignore une.

Type: Guard
Uses: src.utils.source_registry, src.dashboard.utils.kpi_helpers, src.utils.freshness_monitor
Persists in: nothing

Le défaut, mesuré le 2026-09-22
--------------------------------
Deux registres nommaient les mêmes sources, chacun avec sa copie de la table et de la
colonne :

    kpi_helpers.SOURCES_CONFIG        la grille de l'accueil
    freshness_monitor.MONITOR_TARGETS l'alerte nocturne

Sept sources y portaient les mêmes valeurs. **La huitième, iMusician, n'était que dans
le premier** — elle pouvait donc se périmer indéfiniment sans qu'aucune alerte ne le
dise. Et deux tables présentes en production depuis des mois, `hypeddit_daily_stats` et
`sacem_statement`, n'étaient dans NI l'un NI l'autre.

Rien ne rougissait : chaque registre était cohérent avec lui-même. C'est la forme exacte
de la classe « un catalogue recopié » — deux copies ne divergent pas d'un coup, elles
divergent d'une entrée, et la première entrée manquante ne casse rien.

Ce que ce garde NE demande PAS
-------------------------------
⚠️ Il n'exige pas que les deux registres soient identiques. Ils répondent à deux
questions différentes et portent chacun ce qui n'appartient qu'à lui : l'accueil son
icône, son heure et son geste ; l'alerte son seuil, son silence légitime et sa colonne
de MESURE.

Il n'exige pas non plus que la table par LOCATAIRE soit la même. Pour Spotify, l'alerte
lit `track_popularity_history` là où l'accueil lit `artists` à travers le pont
`saas_artists.spotify_artist_id` — une décision écrite, prise après que « quatre
surfaces jugeaient Spotify sur quatre tables différentes ». Le tronc commun s'arrête là
où la question change.

Ce qu'il exige est plus étroit et plus dur : **la table et la colonne du TRONC sont les
mêmes des deux côtés, et aucune source n'est connue d'un seul lecteur.**
"""
from __future__ import annotations

import pytest

from src.dashboard.utils.kpi_helpers import SOURCES_CONFIG
from src.utils.freshness_monitor import MONITOR_TARGETS
from src.utils.source_registry import PAR_CLE, SOURCES, table_et_colonne

_ACCUEIL = {s["label"]: s for s in SOURCES_CONFIG}
_ALERTE = {t["source"]: t for t in MONITOR_TARGETS}


def test_the_registry_is_not_empty() -> None:
    """NON-VACUITÉ. Un registre vidé rendrait zéro paramètre à tout ce qui suit :
    zéro échec, et un garde qui ne garde plus rien en silence.
    """
    assert len(SOURCES) >= 8, (
        f"seulement {len(SOURCES)} source(s) au registre commun — les tests "
        "paramétrés ci-dessous ne vérifieraient presque rien.")


@pytest.mark.parametrize("cle", sorted(PAR_CLE))
def test_both_readers_know_every_source(cle: str) -> None:
    """Une source déclarée est vue par les DEUX lecteurs.

    C'est le défaut exact d'iMusician : présent à l'écran, absent de l'alerte, donc
    périssable sans un mot. L'inverse serait tout aussi faux — une source surveillée
    la nuit et invisible le jour.
    """
    assert cle in _ACCUEIL, (
        f"« {cle} » est au registre commun mais absente de `SOURCES_CONFIG` : "
        "l'artiste ne verra jamais son état, ni ce qu'il faut faire pour la brancher.")
    assert cle in _ALERTE, (
        f"« {cle} » est au registre commun mais absente de `MONITOR_TARGETS` : elle "
        "peut se périmer indéfiniment sans qu'aucune alerte ne le dise. C'est "
        "exactement ce qui est arrivé à iMusician.")


@pytest.mark.parametrize("cle", sorted(PAR_CLE))
def test_both_readers_read_the_same_table_and_column(cle: str) -> None:
    """Le TRONC est identique des deux côtés.

    Deux surfaces qui lisent la fraîcheur d'une même source dans deux tables
    différentes peuvent être vertes et rouges en même temps, toutes les deux
    sincèrement. Ce dépôt l'a vécu sur Spotify — « une seule pouvait être verte sur
    un écran et rouge sur un autre, véridiquement ».
    """
    attendu = table_et_colonne(cle)
    for nom, registre in (("SOURCES_CONFIG", _ACCUEIL), ("MONITOR_TARGETS", _ALERTE)):
        entree = registre.get(cle)
        if entree is None:
            continue      # le test ci-dessus le dit déjà, et mieux
        assert (entree["table"], entree["col"]) == attendu, (
            f"`{nom}` lit « {cle} » dans {(entree['table'], entree['col'])} alors que "
            f"le registre commun dit {attendu}. Une copie a dérivé : les deux "
            "surfaces répondront différemment sur la même source.")


@pytest.mark.parametrize("cle", sorted(PAR_CLE))
def test_neither_reader_invents_a_source(cle: str) -> None:
    """Et la réciproque : aucun lecteur ne connaît une source que le tronc ignore."""
    assert cle in PAR_CLE     # tautologique ici, mais le test suivant ne l'est pas


def test_no_reader_carries_a_source_the_registry_never_declared() -> None:
    """Le sens INVERSE — sans lui, un lecteur pourrait garder sa liste à la main.

    Le test paramétré ci-dessus boucle sur les clés du tronc : il ne verrait jamais
    une entrée ajoutée dans un seul registre sans passer par lui. C'est la moitié du
    prédicat qui manque quand on ne balaie que dans un sens, et ce dépôt a une classe
    pour ça — `a-coherence-checked-in-only-one-direction`.
    """
    for nom, cles in (("SOURCES_CONFIG", set(_ACCUEIL)),
                      ("MONITOR_TARGETS", set(_ALERTE))):
        inconnues = sorted(cles - set(PAR_CLE))
        assert not inconnues, (
            f"`{nom}` porte {inconnues}, que `source_registry` ne déclare pas. La "
            "table et la colonne y sont donc écrites à la main, et rien ne les "
            "compare à l'autre lecteur.")


def test_a_manual_source_is_not_judged_at_the_pace_of_a_robot() -> None:
    """Un seuil d'une semaine sur une saisie mensuelle crie onze mois sur douze.

    C'est la leçon des **85 nuits d'affilée** du 2026-09-14, appliquée aux trois
    sources entrées le 2026-09-22 — distributeur, SACEM, Hypeddit — avant d'avoir à
    la réapprendre. Une alerte toujours rouge apprend à sauter l'alerte.
    """
    from src.utils.freshness_monitor import _MANUAL_STALE_H
    for cle in ("iMusician", "Hypeddit", "SACEM"):
        seuil = _ALERTE[cle]["stale_h"]
        assert seuil >= _MANUAL_STALE_H, (
            f"« {cle} » est surveillée à {seuil} h alors qu'elle est saisie à la main. "
            f"Attendu au moins {_MANUAL_STALE_H} h — sinon elle crie en permanence, et "
            "un lecteur apprend à ignorer le message.")
