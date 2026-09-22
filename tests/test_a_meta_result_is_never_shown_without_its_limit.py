"""Un « résultat » Meta ne s'affiche jamais sans dire que c'est un clic sortant.

Type: Test
Uses: ast, pathlib (aucune base, aucun Streamlit)
Depends on: src/dashboard/**, src/dashboard/utils/proxy_disclosure.py
Persists in: nothing

R146 — le seul P2 du lot du 2026-09-22.

`custom_conversions` est l'évènement que la CAPI d'Hypeddit renvoie **quand
l'auditeur QUITTE le smart link** vers Spotify. Personne ne sait s'il a écouté.
L'app l'affichait partout sous le nom de « résultat » et de « conversion », et en
tirait un « coût par résultat » qui pilote une recommandation de budget.

*Making Websites Win* (Blanks & Jesson) : « If you are only able to track when
someone clicks away from your website, you will optimize your business for
**click-outs, not for conversions**. »

Les deux chiffres qui ne parlent pas de la même chose, déjà au dossier :
**0,130 €** par « résultat », **0,001296 €** par écoute réelle chez le
distributeur. Facteur cent, et aucune page ne le disait.

Le balayage du 2026-09-22 a trouvé **seize grappes de sites vivants** — et
**six sites déjà honnêtes**, tous écrits la veille dans un seul fichier. La forme
correcte existait donc, et elle n'avait pas voyagé.

Classe : `a-proxy-rendered-under-the-name-of-the-thing-it-proxies`.

Ce que ce garde vérifie
-----------------------
Le prédicat porte sur une PROPRIÉTÉ, pas sur une forme d'écriture : un module est
concerné s'il lit une source Meta **et** rend un libellé de coût ou de résultat.
Il passe s'il nomme le clic sortant — par le module canonique
(`proxy_disclosure`, qui rend l'info-bulle et la légende) ou dans ses propres
libellés.

Le premier prédicat écrit pour ce garde attrapait **vingt et un fichiers**, dont
un taux de change USD→EUR, un taux de conversion Hypeddit (clics ÷ visites, qui
est une vraie conversion), et le NOM du menu « CPR Optimizer ». Il cherchait le
mot « CPR » au lieu de chercher « un chiffre Meta rendu à un humain ». C'est très
exactement `a-sweep-predicate-that-matches-a-form-not-a-property`, mesuré dix
fois sur trente balayages dans ce dépôt, et toujours en sur-comptant.

Ce qu'il NE couvre PAS, et c'est dit exprès
--------------------------------------------
· La QUALITÉ de la phrase — un module qui importerait `proxy_disclosure` sans
  jamais appeler ses fonctions passerait. La couverture s'arrête au fait de
  nommer, pas à l'endroit où la phrase atterrit dans la page.
· Les catalogues i18n, exclus du balayage : ils portent des traductions, pas des
  décisions. Leur cohérence est le sujet de `test_i18n.py` — et c'est ce garde-là
  qui a attrapé les quatre catalogues anglais restés au vieux libellé pendant
  que le français était corrigé.
· Un geste voisin non couvert : une NOUVELLE source de proxy (un autre évènement
  CAPI, un « résultat » venant de TikTok Ads) ne déclencherait rien ici tant que
  son nom de table n'est pas dans `_SOURCES_META`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[1] / "src" / "dashboard"

# La PROPRIÉTÉ, moitié 1 : le module lit une source Meta.
_SOURCES_META = re.compile(
    r"v_meta_daily|v_meta_campaign_daily|meta_insights|meta_campaigns"
    r"|meta_ads\b|custom_conversions"
)

# La PROPRIÉTÉ, moitié 2 : il rend un libellé de coût ou de résultat.
_LIBELLE = re.compile(r"\bCPR\b|Résultats?\b|\bResults\b|Clics sortants|Outbound clicks")

# Ce qui vaut « la limite est nommée » dans les libellés du module lui-même.
_NOMME_LE_CLIC = re.compile(r"clic[s]? sortant|outbound click", re.I)

_MODULE_CANONIQUE = "proxy_disclosure"


def _libelles(chemin: Path) -> list[str]:
    """Les littéraux courts du module — jamais son SQL ni ses docstrings de bloc.

    On passe par l'AST plutôt que par le texte : un commentaire qui PARLE du
    défaut ne doit pas satisfaire le garde. Ce dépôt a pris quatre gardes au vert
    sur leur propre commentaire en une soirée (2026-08-22).
    """
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    return [
        n.value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and len(n.value) < 80
        and not n.value.startswith(("SELECT", "\n", "FROM"))
        and _LIBELLE.search(n.value)
    ]


def _modules_concernes() -> list[Path]:
    out = []
    for f in sorted(_RACINE.rglob("*.py")):
        if "i18n_catalog" in str(f) or f.name == f"{_MODULE_CANONIQUE}.py":
            continue
        txt = f.read_text(encoding="utf-8")
        if _SOURCES_META.search(txt) and _libelles(f):
            out.append(f)
    return out


def test_the_predicate_is_not_vacuous():
    """Un balayage qui ne trouve rien passe pour toujours et ne garde rien.

    Onze modules étaient concernés le 2026-09-22. Le plancher est à cinq : il
    attrape une refonte qui viderait le balayage sans corriger quoi que ce soit.
    """
    concernes = _modules_concernes()
    assert len(concernes) >= 5, (
        f"seulement {len(concernes)} module(s) concerné(s) — le prédicat ne voit "
        "plus les surfaces Meta. Vérifier `_SOURCES_META` avant de croire ce vert."
    )


def test_the_predicate_does_not_catch_an_unrelated_conversion_rate():
    """Le faux positif à écarter, nommé — trois vrais cas du dépôt.

    Un taux de change USD→EUR, un taux de conversion Hypeddit (clics ÷ visites,
    qui est une VRAIE conversion), et le nom du menu « CPR Optimizer » ne sont pas
    ce défaut. Si le prédicat les rattrape, il est redevenu textuel.
    """
    noms = {f.name for f in _modules_concernes()}
    for innocent in ("upload_csv.py", "referral_admin.py", "hypeddit.py",
                     "nav_sections.py", "i18n.py"):
        assert innocent not in noms, (
            f"{innocent} est attrapé par le prédicat : il ne rend aucun « résultat » "
            "Meta. Le prédicat cherche une forme d'écriture, pas une propriété."
        )


def test_every_meta_result_surface_names_the_outbound_click():
    """Le garde lui-même."""
    muets = []
    for f in _modules_concernes():
        txt = f.read_text(encoding="utf-8")
        if _MODULE_CANONIQUE in txt:
            continue                       # il rend l'info-bulle canonique
        if any(_NOMME_LE_CLIC.search(lab) for lab in _libelles(f)):
            continue                       # il le nomme dans ses propres libellés
        muets.append(str(f.relative_to(_RACINE.parents[1])))
    assert not muets, (
        "ces surfaces rendent un « résultat » ou un CPR Meta sans jamais nommer le "
        "clic sortant :\n  " + "\n  ".join(muets)
        + "\n\nSoit importer `src/dashboard/utils/proxy_disclosure.py` (info-bulle "
          "`cpr_help()`, légende `disclosure_caption()`, PDF `pdf_disclosure()`), "
          "soit écrire « clic sortant » dans le libellé lui-même."
    )


def test_the_canonical_module_holds_the_sentence_once():
    """La phrase vit à UN endroit — la recopier est ce qui a créé le défaut.

    Le DEVLOG du 2026-09-22 porte le précédent : « un catalogue recopié trois
    fois » a produit deux promesses fausses tenues dix-sept jours.
    """
    canon = _RACINE / "utils" / f"{_MODULE_CANONIQUE}.py"
    assert canon.exists(), f"{canon} a disparu — la phrase n'a plus de source unique"
    txt = canon.read_text(encoding="utf-8")
    for fonction in ("cpr_help", "disclosure_caption", "pdf_disclosure",
                     "outbound_help"):
        assert f"def {fonction}(" in txt, f"{fonction}() a disparu du module canonique"


# ── Le garde se prouve lui-même ───────────────────────────────────────────────
#
# Un prédicat qu'on n'a vu mordre que sur l'arbre réel ne dit rien de ce qu'il
# ferait sur un arbre corrigé, ni de ce qu'il rate. Ces deux tests fabriquent le
# défaut et sa forme honnête, et exigent que le détecteur distingue les deux.

def _module_synthetique(tmp_path, source: str):
    """Écrit un module jetable et rend (est_concerné, nomme_le_clic)."""
    f = tmp_path / "vue_jetable.py"
    f.write_text(source, encoding="utf-8")
    libs = _libelles(f)
    concerne = bool(_SOURCES_META.search(source) and libs)
    nomme = any(_NOMME_LE_CLIC.search(lab) for lab in libs)
    return concerne, nomme


_DEFAUT = '''
import streamlit as st

def show(db):
    d = db.fetch_df("SELECT SUM(custom_conversions) c FROM v_meta_campaign_daily")
    st.metric("Résultats", int(d["c"][0]))
    st.metric("CPR", "0.13 €")
'''

_HONNETE = '''
import streamlit as st

def show(db):
    d = db.fetch_df("SELECT SUM(custom_conversions) c FROM v_meta_campaign_daily")
    st.metric("Clics sortants", int(d["c"][0]))
    st.metric("CPR (€/clic sortant)", "0.13 €")
'''


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path):
    concerne, nomme = _module_synthetique(tmp_path, _DEFAUT)
    assert concerne, "un module qui lit Meta et affiche « Résultats » doit être concerné"
    assert not nomme, "il ne nomme nulle part le clic sortant — il doit être signalé"


def test_the_corrected_form_leaves_the_detector_silent(tmp_path):
    """La réciproque, et elle compte autant.

    Sans elle, un prédicat qui rendrait « concerné » pour TOUT passerait le test
    précédent et serait inutilisable.
    """
    concerne, nomme = _module_synthetique(tmp_path, _HONNETE)
    assert concerne, "il lit toujours une source Meta — il reste dans le périmètre"
    assert nomme, "il nomme le clic sortant dans ses libellés — il ne doit pas être signalé"


def test_a_module_that_never_touches_meta_is_out_of_scope(tmp_path):
    """Le faux positif synthétique : un « résultat » qui n'est pas celui de Meta."""
    source = '''
import streamlit as st

def show(db):
    d = db.fetch_df("SELECT count(*) c FROM s4a_song_timeline")
    st.metric("Résultats du mois", int(d["c"][0]))
'''
    concerne, _nomme = _module_synthetique(tmp_path, source)
    assert not concerne, (
        "un module qui ne lit aucune source Meta ne relève pas de cette classe — "
        "le prédicat cherche une propriété, pas le mot « Résultats »"
    )
