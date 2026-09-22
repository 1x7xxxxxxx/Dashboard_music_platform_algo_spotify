"""Un chiffre de campagne porte sa date, et l'écran dit depuis quand rien ne tourne.

Type: Guard
Uses: ast, streamlit.testing, src.dashboard.views.home_meta_advice
Depends on: src/dashboard/views/home_meta_advice.py, src/dashboard/utils/period_side_metrics.py
Persists in: nothing

LE CHIFFRE QUI A DÉCIDÉ — relevé EN PRODUCTION le 2026-09-22
-------------------------------------------------------------
`meta_insights_performance_day` porte, pour les deux seuls locataires qui ont de la
donnée Meta :

    MAX(day_date)      2024-09-30      la dernière journée où une campagne a dépensé
    MAX(collected_at)  2026-09-22      le JOUR MÊME — le DAG réécrit chaque matin les
                                       mêmes lignes de 2024
    écart              722 jours

Et `meta_campaigns` porte **19 ARCHIVED + 15 PAUSED, zéro ACTIVE**.

L'accueil affichait « ta campagne la moins chère est X : 0,109 € le clic sortant ».
Le coût était juste ; **le temps de la phrase était faux.** Un artiste lisait au présent
un relevé de deux ans, sans rien à l'écran pour le lui dire.

TROIS ÉTATS, ET ILS NE SE CONFONDENT PAS
-----------------------------------------
C'est la règle « une lecture qui échoue ne se déguise pas en rien à lire »
(`.claude/rules/python.md`) appliquée à un écran :

    une campagne tourne          → SILENCE. Annoncer « tout va bien » à chaque rendu
                                   apprend à sauter la ligne.
    aucune, et on le SAIT        → on le dit, avec la date de la dernière dépense.
                                   `meta_campaigns` porte des lignes, aucune ACTIVE.
    on ne SAIT pas               → la date seule. `meta_campaigns` est vide pour ce
                                   locataire alors que la dépense existe (l'artiste 18
                                   en production). Écrire « aucune campagne active »
                                   serait une affirmation qu'aucune donnée ne soutient.

POURQUOI LE STATUT ET PAS LA DATE
----------------------------------
« La dernière dépense est vieille » et « aucune campagne ne tourne » sont deux faits
distincts : une campagne `ACTIVE` à budget épuisé ne dépense plus et tourne toujours. La
source de vérité est `meta_campaigns.status`, celle que `freshness_monitor` prend déjà
pour taire son alerte `meta_no_active_campaign`. On ne s'en invente pas une seconde.

⚠️ CE QU'IL NE TIENT PAS
------------------------
* **La FRAÎCHEUR de `meta_campaigns` elle-même.** Si ce catalogue cesse d'être collecté,
  ses statuts se figent et l'écran affirmera « aucune active » sur un état périmé. La
  table a sa propre surveillance ; ce garde n'y touche pas.
* **Le geste voisin le plus proche : les autres chiffres de l'accueil qui n'ont pas de
  date.** Shazam, Hypeddit, SACEM et iMusician sont dans le même cas et ne sont PAS
  couverts ici. R157 porte la question au niveau de la grille de fraîcheur.
* **La JUSTESSE de `MAX(day)`** : c'est la dernière journée de DÉPENSE, pas la dernière
  journée où la campagne existait.
"""
from __future__ import annotations

import ast
import datetime
import os
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_VUE = _ROOT / "src" / "dashboard" / "views" / "home_meta_advice.py"
_REQ = _ROOT / "src" / "dashboard" / "utils" / "period_side_metrics.py"

_BASE = dict(
    meta_spend=3087.82,
    best_cpr=0.10899,
    best_cpr_name="O chiotte l'arbitre Tucome Back",
    best_cpr_spend=755.52,
    axe_age=None, axe_pays=None, axe_placement=None,
)


def _rendu(**extra):
    """Le bloc RENDU pour de vrai, et les éléments dans l'ordre de l'écran."""
    from streamlit.testing.v1 import AppTest

    side = {**_BASE, **extra}
    src = (
        f"import sys; sys.path.insert(0, {str(_ROOT)!r})\n"
        "import streamlit as st, datetime\n"
        "st.session_state['role']='artist'; st.session_state['artist_id']=1\n"
        "st.session_state['authenticated']=True; st.session_state['email']='a@t'\n"
        f"side = {side!r}\n"
        "from src.dashboard.views.home_meta_advice import render_meta_advice\n"
        "render_meta_advice(side)\n"
    )
    at = AppTest.from_string(src)
    at.run(timeout=180)
    assert not at.exception, f"le bloc lève : {at.exception}"

    def plat(n, out=None):
        out = [] if out is None else out
        k = getattr(n, "children", None)
        for c in (k.values() if isinstance(k, dict) else (k or [])):
            out.append(c)
            plat(c, out)
        return out

    els = plat(at.main)
    textes = [str(getattr(e, "value", "") or getattr(e, "body", "")
                  or getattr(e, "label", "")) for e in els]
    return at, els, textes


_HIER = datetime.date.today() - datetime.timedelta(days=1)
_VIEUX = datetime.date(2024, 9, 30)


# ══════════════════════════════════════════════════════════════════════════
# 1. LA DATE VOYAGE AVEC LE CHIFFRE
# ══════════════════════════════════════════════════════════════════════════

def test_a_dated_figure_shows_its_date() -> None:
    """Sans date, « 0,109 € le clic » se lit au présent — et il a 722 jours.

    ⚠️ LA DATE EST CHERCHÉE SUR LA LIGNE DU CHIFFRE, pas dans le texte joint de
    l'écran. Le premier jet joignait tous les éléments et cherchait « 30/09/2024 »
    dedans : l'encart d'activité, plus bas, porte la MÊME date, donc retirer la date
    de la ligne du chiffre laissait le test **VERT**. Trouvé en mutant, et c'est le
    mode d'échec que ce dépôt appelle
    `a-sweep-predicate-that-matches-a-form-not-a-property` — chercher une chaîne
    quelque part au lieu de la propriété « CE chiffre porte SA date ».
    """
    _at, _els, textes = _rendu(best_cpr_last_day=_VIEUX, meta_last_day=_VIEUX,
                               meta_active=0, meta_campaigns_known=34)
    ligne = next((x for x in textes if _BASE["best_cpr_name"] in x
                  and "0,109" in x), None)
    assert ligne is not None, (
        "la ligne qui nomme la campagne et son coût a disparu de l'écran. Rendu :\n"
        + "\n".join(t for t in textes if t)[:600])
    assert "30/09/2024" in ligne, (
        "le coût par résultat est affiché SANS la date de la dernière dépense de sa "
        "campagne, SUR SA PROPRE LIGNE. En production c'est le 30/09/2024, soit "
        "722 jours : le chiffre est juste et la phrase est au présent. La ligne "
        f"rendue :\n    {ligne}")


def test_the_figure_still_shows_without_a_date() -> None:
    """NON-VACUITÉ inverse : sans date connue, le bloc ne disparaît pas.

    Un garde qui exigerait la date sans ce test pousserait à masquer le chiffre quand
    la date manque — du code correct qui n'affiche plus rien.
    """
    _at, _els, textes = _rendu(best_cpr_last_day=None, meta_last_day=None,
                               meta_active=0, meta_campaigns_known=0)
    joint = "\n".join(textes)
    assert "0,109" in joint, (
        "sans date, le coût par résultat n'est plus affiché du tout : le garde de la "
        f"date a fait disparaître le chiffre. Rendu :\n{joint[:400]}")


# ══════════════════════════════════════════════════════════════════════════
# 2. LES TROIS ÉTATS, ET ILS SE DISTINGUENT
# ══════════════════════════════════════════════════════════════════════════

def test_a_running_campaign_says_nothing() -> None:
    """LE SILENCE EST LE BON MESSAGE quand tout va bien.

    Une confirmation à chaque rendu apprend à sauter la ligne — c'est la leçon des
    85 nuits d'alerte de `freshness_monitor`, appliquée à un écran.
    """
    at, _els, textes = _rendu(best_cpr_last_day=_HIER, meta_last_day=_HIER,
                              meta_active=2, meta_campaigns_known=5)
    # ⚠️ L'ANCRE D'ABORD, et c'est MON garde du matin qui l'a exigé : un écran
    # effondré n'affiche aucun encart, donc `assert not at.info` est vraie sur le vide
    # — satisfaite par la panne qu'elle devrait attraper. Classe
    # `a-guard-satisfied-by-the-collapse-it-should-catch`, et je l'ai commise le jour
    # même où j'ai écrit son garde, dans le fichier d'à côté.
    assert any(_BASE["best_cpr_name"] in x for x in textes), (
        "le bloc ne rend plus la ligne de sa campagne : la surface est effondrée, et "
        "l'absence d'encart vérifiée ci-dessous ne prouverait rien.")
    assert not list(at.info), (
        "une campagne tourne et l'écran affiche quand même un encart : "
        f"{[str(getattr(e, 'value', '')) for e in at.info]}")


def test_no_active_campaign_is_said_with_its_date() -> None:
    """L'état que la production porte aujourd'hui, et la demande explicite."""
    at, _els, textes = _rendu(best_cpr_last_day=_VIEUX, meta_last_day=_VIEUX,
                              meta_active=0, meta_campaigns_known=34)
    encarts = [str(getattr(e, "value", "") or getattr(e, "body", ""))
               for e in at.info]
    assert encarts, (
        "aucune campagne n'est active et l'écran ne le dit pas : les chiffres "
        "ci-dessus se lisent au présent.")
    joint = "\n".join(encarts)
    # ⚠️ L'ANCIENNETÉ SE CALCULE, ELLE NE SE FIGE PAS. Ce test épinglait « 722 » — le
    # nombre de jours écoulés le 2026-09-22. Il est devenu rouge le LENDEMAIN, à 723,
    # sans qu'aucune ligne de code ait bougé : un test qui fige une grandeur dépendant
    # de l'horloge se périme chaque nuit, et son rouge n'apprend rien.
    #
    # C'est la même erreur que celle que ce dépôt appelle
    # `a-prose-claim-that-cannot-be-verified`, transposée à une assertion : un chiffre
    # écrit à la main là où une mesure était disponible.
    attendu = (datetime.date.today() - _VIEUX).days
    assert "30/09/2024" in joint and str(attendu) in joint, (
        f"l'encart ne porte pas la date et l'ancienneté ({attendu} j) : {joint}")
    assert "active" in joint.lower(), (
        f"l'encart ne dit pas que rien ne tourne : {joint}")


def test_an_unknown_campaign_list_does_not_claim_nothing_runs() -> None:
    """LA DISTINCTION QUI COMPTE : « absent » n'est pas « aucune ».

    `meta_campaigns` est VIDE pour l'artiste 18 en production, alors que sa dépense
    existe. Affirmer « aucune campagne n'est active » serait une affirmation qu'aucune
    donnée ne soutient — et c'est précisément le défaut que ce dépôt a payé plusieurs
    fois sous le nom « une table vide se lit comme pas encore de données ».
    """
    at, _els, _t = _rendu(best_cpr_last_day=_VIEUX, meta_last_day=_VIEUX,
                          meta_active=0, meta_campaigns_known=0)
    encarts = [str(getattr(e, "value", "") or getattr(e, "body", ""))
               for e in at.info]
    assert encarts, "sans liste de campagnes, l'écran ne date même plus la dépense"
    joint = "\n".join(encarts)
    assert "30/09/2024" in joint, f"la date manque : {joint}"
    assert "aucune campagne n'est active" not in joint.lower(), (
        "l'écran affirme « aucune campagne n'est active » alors que la liste des "
        f"campagnes est VIDE : rien ne soutient cette phrase. Rendu : {joint}")


def test_the_three_states_are_distinguishable() -> None:
    """NON-VACUITÉ D'ENSEMBLE : trois états, trois rendus différents.

    Sans ce test, une implémentation qui rendrait le même encart partout — ou aucun —
    passerait les trois tests ci-dessus dès que l'un d'eux serait assoupli.
    """
    rendus = []
    for cas in (dict(meta_active=2, meta_campaigns_known=5),
                dict(meta_active=0, meta_campaigns_known=34),
                dict(meta_active=0, meta_campaigns_known=0)):
        at, _e, _t = _rendu(best_cpr_last_day=_VIEUX, meta_last_day=_VIEUX, **cas)
        rendus.append("|".join(str(getattr(x, "value", "") or getattr(x, "body", ""))
                               for x in at.info))
    assert len(set(rendus)) == 3, (
        f"les trois états ne produisent que {len(set(rendus))} rendu(s) distinct(s) : "
        f"{rendus}")


# ══════════════════════════════════════════════════════════════════════════
# 3. LE PLAFOND, ET LA REQUÊTE
# ══════════════════════════════════════════════════════════════════════════

def test_the_block_draws_no_gauge() -> None:
    """`home_tiles.py` est à 6 jauges sur 6 : ce bloc n'en ajoute aucune."""
    at, _els, textes = _rendu(best_cpr_last_day=_VIEUX, meta_last_day=_VIEUX,
                              meta_active=0, meta_campaigns_known=34)
    # Même raison : « zéro jauge » est vrai d'un écran vide. On ancre sur la ligne de
    # la campagne, qui est précisément ce que ce bloc rend EN PHRASES au lieu d'une
    # jauge.
    #
    # ⚠️ La première ancre visait le NOMBRE formaté (« 3 088 ») et elle a rougi : le
    # séparateur de milliers n'est pas l'espace que j'avais tapé. Ancrer sur un nombre
    # mis en forme fait dépendre le garde d'une décision de présentation ; le nom de la
    # campagne est la donnée, pas sa typographie.
    assert any(_BASE["best_cpr_name"] in x for x in textes), (
        "le bloc ne rend plus la ligne de sa campagne : sur une surface effondrée, "
        "« zéro jauge » serait vrai pour rien.")
    assert not list(at.metric), (
        f"{len(list(at.metric))} `st.metric` dans ce bloc — le premier écran est "
        "plafonné et ce bloc est en phrases, par décision du 2026-09-22.")


def test_the_last_spend_day_is_read_outside_the_period_window() -> None:
    """LE PIÈGE, et il rendrait la ligne circulaire.

    Les autres sous-requêtes de `period_side_metrics` sont bornées par la période —
    elles répondent à « combien sur la fenêtre ». Celle-ci répond à « depuis quand
    n'y a-t-il plus rien », et une borne la rendrait circulaire : sur une fenêtre de
    30 jours elle renverrait NULL pour un catalogue arrêté il y a deux ans, donc
    exactement dans le cas qu'elle existe pour nommer.

    Par l'AST : la sous-requête `MAX(day) FROM v_meta_daily` ne porte aucun `%s::date`.
    """
    src = _REQ.read_text(encoding="utf-8")
    i = src.find("MAX(day) FROM v_meta_daily")
    assert i > 0, (
        "la sous-requête `MAX(day) FROM v_meta_daily` a disparu : l'écran ne peut plus "
        "dater la dernière dépense.")
    # La sous-requête s'arrête à sa parenthèse fermante / son alias.
    fin = src.find("AS meta_last_day", i)
    assert fin > i, "l'alias `meta_last_day` a disparu de la requête."
    fragment = src[i:fin]
    assert "::date" not in fragment, (
        "la sous-requête de la dernière dépense est BORNÉE par la période :\n"
        f"    {fragment.strip()}\n\n"
        "Elle rendrait NULL sur une fenêtre de 30 jours pour un catalogue arrêté il y "
        "a deux ans — le cas exact qu'elle existe pour nommer.")


def test_the_status_comes_from_the_campaign_catalogue() -> None:
    """Le statut se LIT, il ne s'infère pas d'une date.

    Une campagne `ACTIVE` à budget épuisé ne dépense plus et tourne toujours : la date
    de dernière dépense ne peut pas répondre à « est-ce que ça tourne ».
    """
    src = _REQ.read_text(encoding="utf-8")
    tree = ast.parse(src)
    litteraux = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    sql = "\n".join(litteraux)
    assert "meta_campaigns" in sql and "'ACTIVE'" in sql, (
        "le statut des campagnes ne vient plus de `meta_campaigns.status` : l'écran "
        "l'infère donc d'autre chose, et « la dépense est vieille » n'est pas « rien "
        "ne tourne ».")


def test_the_view_needs_no_database() -> None:
    """Ce module reste SANS requête : il reçoit `side`, il ne lit rien.

    C'est ce qui garantit structurellement que le bloc coûte zéro requête. Vérifié par
    la SIGNATURE, pas par l'intention.
    """
    import inspect

    from src.dashboard.views.home_meta_advice import render_meta_advice

    params = set(inspect.signature(render_meta_advice).parameters)
    assert params == {"side"}, (
        f"`render_meta_advice` prend {sorted(params)} — un `db` ou un `artist_id` dans "
        "cette signature, et le bloc peut interroger la base. Le compte de requêtes de "
        "l'accueil est un cliquet à 14 sur 14.")


def test_the_files_the_ast_tests_read_still_exist() -> None:
    """Garde-fou de collecte : les deux fichiers lus par chemin existent et s'analysent.

    ⚠️ Ce test s'appelait `..._is_not_in_the_env`, un nom qui ne décrivait rien de ce
    qu'il vérifie — et il prenait un `tmp_path` dont il ne se servait pas. Renommé le
    2026-09-22, troisième occurrence du jour de « un nom qui promet plus que son
    prédicat » après le screenshot Spotify et l'allowlist d'activation.

    Trivial en apparence, et il a une raison : les deux tests AST ci-dessus lisent
    `period_side_metrics.py` par chemin. Si le fichier bougeait, ils lèveraient au lieu
    de rougir, et une erreur de collecte se lit moins bien qu'un échec nommé.
    """
    assert _VUE.is_file(), f"{_VUE} a disparu"
    assert _REQ.is_file(), f"{_REQ} a disparu"
    ast.parse(_REQ.read_text(encoding="utf-8"))
    ast.parse(_VUE.read_text(encoding="utf-8"))
