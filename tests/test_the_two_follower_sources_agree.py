"""Les deux relevés d'abonnés mesurent-ils la même chose ?

Type: Guard
Uses: src.dashboard.utils.followers_agreement, live Postgres (optionnel)
Depends on: v_spotify_followers_daily, views/spotify_s4a_combined.py
Persists in: nothing

LA FUSION EST CONDITIONNELLE, ET CE FICHIER EST LA CONDITION — 2026-09-23
--------------------------------------------------------------------------
La figure traçait DEUX courbes d'abonnés, le CSV Spotify for Artists et l'API, jamais
raboutées. Demandé : « ne mets pas 2 sources pour abonnés, mets en place un garde qui
nous confirme que les 2 sont bien les mêmes sinon alerte ».

**La mesure donne raison à la demande**, relevée sur l'artiste 1 le 2026-09-23 :

    s4a_csv        889 jours   2024-01-01 → 2026-06-07
    spotify_api     48 jours   2025-11-23 → 2026-09-20
    jours communs   32 · divergents 5 · **écart maximum 1 abonné** sur ~684 (0,15 %)

⚠️ MAIS « ELLES S'ACCORDENT AUJOURD'HUI » N'EST PAS « ELLES S'ACCORDERONT ». C'est
précisément ce que la demande a vu : raccorder deux sources sans rien qui surveille le
raccord fabrique une courbe qui mentira le jour où l'une dérivera — et qui mentira EN
SILENCE, parce qu'une courbe lisse ne dit jamais qu'elle est cousue.

DEUX SURFACES D'ALERTE, ET ELLES NE SE REMPLACENT PAS
------------------------------------------------------
* **ce fichier** : rouge en CI dès que les deux sources s'écartent au-delà de la
  tolérance sur la base vivante. C'est ce qui arrête une livraison ;
* **la vue** : un `st.warning` au-dessus de la figure, visible par l'ARTISTE, qui est le
  seul à pouvoir relancer un import. Il est MUET tant que tout va bien — une
  confirmation permanente s'apprend à sauter, et c'est la leçon des 85 nuits d'alerte de
  `freshness_monitor`.

⚠️ CE QU'IL NE TIENT PAS
------------------------
1. **Une dérive LENTE.** Deux sources qui s'écartent d'un abonné par mois restent sous
   le seuil pendant des années. Ce garde attrape une RUPTURE, pas un glissement.
2. **Le geste voisin le plus proche : les autres séries à deux sources.** Les écoutes
   viennent du CSV et l'indice de popularité de l'API, sur la même page, et rien ne
   compare ces deux-là — elles ne mesurent pas la même grandeur, donc il n'y a rien à
   comparer, mais une troisième paire qui apparaîtrait ne serait pas vue ici.
3. **Le cas « plus aucun jour commun ».** Si les deux sources cessent de se recouvrir,
   il n'y a plus rien à comparer. Le module rend alors `accord=False` — « on ne sait
   pas » n'est pas « elles s'accordent » — et ce fichier le vérifie explicitement.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.dashboard.utils.followers_agreement import (
    TOLERANCE_ABSOLUE, TOLERANCE_RELATIVE, comparer)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VUE = _ROOT / "src" / "dashboard" / "views" / "spotify_s4a_combined.py"


# ══════════════════════════════════════════════════════════════════════════
# 1. LE COMPARATEUR — testable sans base
# ══════════════════════════════════════════════════════════════════════════

def test_two_identical_sources_agree() -> None:
    """Le cas nominal, et la NON-VACUITÉ de tout ce qui suit."""
    lignes = [(d, s, 100 + d) for d in range(10) for s in ("s4a_csv", "spotify_api")]
    a = comparer(lignes)
    assert a.jours_communs == 10
    assert a.jours_divergents == 0
    assert a.ecart_max == 0
    assert a.accord is True


def test_a_one_follower_gap_is_tolerated() -> None:
    """L'écart RÉEL du catalogue au 2026-09-23 : 1 abonné sur 685.

    C'est un décalage d'heure de relevé — le CSV est un instantané d'export, l'API lit
    à son heure de cron. Le refuser ferait crier le garde tous les jours sur un
    fonctionnement correct, ce que ce dépôt a déjà payé 85 nuits d'affilée.
    """
    a = comparer([(1, "s4a_csv", 685), (1, "spotify_api", 684)])
    assert a.ecart_max == 1
    assert a.accord is True, f"un écart de 1 abonné est refusé : {a}"


def test_a_real_divergence_is_caught() -> None:
    """LE DÉFAUT QUE CE GARDE EXISTE POUR VOIR : une rupture entre les deux relevés."""
    a = comparer([(1, "s4a_csv", 685), (1, "spotify_api", 500)])
    assert a.ecart_max == 185
    assert a.accord is False, (
        "un écart de 185 abonnés passe pour un accord : la courbe unique serait cousue "
        f"sur deux mesures incompatibles sans que rien ne le dise. {a}")


def test_the_threshold_follows_the_size_of_the_account() -> None:
    """Un seuil FIXE sur une grandeur qui change d'ordre se périme sans le dire.

    0,5 % vaut 3 sur 685 abonnés et 340 sur 68 000. Un seuil absolu calibré sur le
    premier crierait sur le second au moindre décalage d'heure —
    `un-seuil-écrit-d-instinct`, neuf classes au catalogue.
    """
    petit = comparer([(1, "s4a_csv", 685), (1, "spotify_api", 685 - 10)])
    assert petit.accord is False, "10 d'écart sur 685 devrait être refusé"
    gros = comparer([(1, "s4a_csv", 68000), (1, "spotify_api", 68000 - 10)])
    assert gros.accord is True, (
        "10 d'écart sur 68 000 est refusé : le seuil ne suit pas la taille du compte.")
    assert TOLERANCE_RELATIVE > 0 and TOLERANCE_ABSOLUE > 0


def test_no_common_day_is_not_an_agreement() -> None:
    """« On ne sait pas » n'est pas « elles s'accordent ».

    Si les deux sources cessent de se recouvrir, il n'y a plus rien à comparer. Rendre
    `accord=True` ferait passer l'absence de preuve pour une preuve — c'est la règle
    « une lecture qui échoue ne se déguise pas en rien à lire », appliquée à un
    comparateur.
    """
    a = comparer([(1, "s4a_csv", 685), (2, "spotify_api", 684)])
    assert a.jours_communs == 0
    assert a.accord is False, (
        "aucun jour commun et pourtant « accord » : l'absence de preuve passe pour une "
        f"preuve. {a}")


def test_a_missing_value_is_not_a_zero() -> None:
    """Un `None` n'entre pas dans la comparaison comme un compte de zéro."""
    a = comparer([(1, "s4a_csv", 685), (1, "spotify_api", None)])
    assert a.jours_communs == 0, f"un `None` a été compté comme une valeur : {a}"


# ══════════════════════════════════════════════════════════════════════════
# 2. LA BASE VIVANTE — l'alerte qui arrête une livraison
# ══════════════════════════════════════════════════════════════════════════

def test_the_live_sources_still_agree() -> None:
    """Rouge en CI dès que les deux relevés s'écartent en PRODUCTION.

    C'est la moitié qui arrête une livraison. L'autre est le `st.warning` de la vue, que
    l'artiste voit — et lui seul peut relancer un import.
    """
    from tests.db_gate import db_ready, dsn

    if not db_ready():
        pytest.skip("Postgres injoignable — l'accord de deux sources ne se lit pas "
                    "dans le code")
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**dsn(), connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT artist_id FROM v_spotify_followers_daily")
            artistes = [r[0] for r in cur.fetchall()]
            fautifs = []
            vus = 0
            for aid in artistes:
                cur.execute(
                    "SELECT day, source, followers FROM v_spotify_followers_daily "
                    "WHERE artist_id = %s", (aid,))
                a = comparer(cur.fetchall())
                if not a.jours_communs:
                    continue          # rien à comparer : ce n'est pas un désaccord
                vus += 1
                if not a.accord:
                    fautifs.append(
                        f"artiste {aid} : {a.ecart_max} d'écart le {a.jour_pire} "
                        f"(niveau {a.niveau_pire}, toléré {a.tolerance_au_pire:.1f})")
    finally:
        conn.close()

    assert not fautifs, (
        "les deux relevés d'abonnés ne concordent plus :\n"
        + "\n".join(f"    {f}" for f in fautifs)
        + "\n\nLa figure n'en trace plus qu'UNE seule courbe depuis le 2026-09-23, et "
          "cette fusion suppose qu'elles mesurent la même chose. Vérifier l'import CSV "
          "et la collecte API avant de recoudre.")
    if vus == 0:
        pytest.skip("aucun locataire n'a deux sources qui se recouvrent aujourd'hui")


# ══════════════════════════════════════════════════════════════════════════
# 3. LA VUE — une seule courbe, et une alerte qui peut parler
# ══════════════════════════════════════════════════════════════════════════

def test_the_figure_draws_one_follower_curve() -> None:
    """Deux courbes demandaient au lecteur un travail dont la réponse est toujours non."""
    tree = ast.parse(_VUE.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None, "`_engagement_fig` a disparu"
    scatters = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", None) == "add_trace" and n.args
                and getattr(getattr(n.args[0], "func", None), "attr", None) == "Scatter"]
    assert len(scatters) == 1, (
        f"{len(scatters)} courbes d'abonnés au lieu d'une. La fusion du 2026-09-23 "
        "suppose que les deux sources mesurent la même chose — ce que "
        "`test_the_live_sources_still_agree` vérifie.")


def test_the_view_can_speak_when_they_diverge() -> None:
    """La fusion sans l'alerte fabriquerait une courbe qui ment EN SILENCE.

    Par l'AST : la vue appelle le comparateur, et un `st.warning` dépend de son verdict.
    """
    tree = ast.parse(_VUE.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None
    appelle = any(isinstance(n, ast.Call) and getattr(n.func, "id", None) == "comparer"
                  for n in ast.walk(fn))
    assert appelle, (
        "la vue ne compare plus les deux sources : la courbe unique est cousue sans que "
        "rien ne surveille le raccord.")
    alerte = any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "warning"
                 for n in ast.walk(fn))
    assert alerte, (
        "la vue ne peut plus alerter : le détecteur tourne et personne ne l'entend.")


def test_the_alert_is_silent_when_they_agree() -> None:
    """Muette tant que tout va bien — une confirmation permanente s'apprend à sauter.

    Par l'AST : le `warning` est SOUS une condition, jamais au niveau de la fonction.
    """
    tree = ast.parse(_VUE.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_engagement_fig"), None)
    assert fn is not None
    # ⚠️ LA CONDITION DOIT DÉPENDRE DU VERDICT, pas seulement exister. Mon premier
    # jet vérifiait « le `warning` vit sous un `ast.If` » : remplacer la condition par
    # `if True:` laissait le test VERT alors que l'alerte s'affichait à chaque rendu.
    # Trouvé en mutant — quatrième fois de la journée que je cherche une FORME là où la
    # classe parle d'une PROPRIÉTÉ
    # (`a-sweep-predicate-that-matches-a-form-not-a-property`).
    gouvernees = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.If):
            continue
        if not any(isinstance(c, ast.Call)
                   and getattr(c.func, "attr", None) == "warning"
                   for c in ast.walk(n.body[0]) if n.body):
            # le `warning` doit être DANS la branche, pas ailleurs sous le `if`
            if not any(isinstance(c, ast.Call)
                       and getattr(c.func, "attr", None) == "warning"
                       for b in n.body for c in ast.walk(b)):
                continue
        noms = {x.id for x in ast.walk(n.test) if isinstance(x, ast.Name)}
        attrs = {getattr(x, "attr", "") for x in ast.walk(n.test)}
        if "accord" in noms or "accord" in attrs:
            gouvernees.append(n.lineno)
    assert gouvernees, (
        "l'alerte de divergence ne dépend plus du VERDICT de la comparaison : elle "
        "s'affiche quelle que soit la réponse. Une phrase qui apparaît toujours cesse "
        "d'être lue — ce dépôt a payé 85 nuits d'alerte pour l'apprendre.")
