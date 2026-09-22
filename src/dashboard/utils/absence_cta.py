"""Une source vide dit ce qui devrait être là, et porte le bouton qui y mène.

Type: Sub
Uses: streamlit, navigation.goto, stripe_schema.page_is_locked
Depends on: le champ `page` / `valeur` / `geste` de kpi_helpers.SOURCES_CONFIG
Triggers: views/home.py
Persists in: nothing

Le trou, balayé le 2026-09-22
------------------------------
Une source sans donnée affichait « — » et s'arrêtait. Pour quatre artistes bêta sur
six, l'accueil était donc un écran de tirets sans une seule indication de quoi faire.

Et le dépôt savait déjà quoi dire : **neuf messages** nommaient une page en toutes
lettres, dans une chaîne française codée en dur, **sans jamais y mener** —
`home.py:164`, `home_tiles.py:237`, `home_tiles.py:346`, `onboarding_health.py:171`,
`credentials/_platform_soundcloud.py:196`, `trigger_algo/_tab_catalogue.py:94`,
`trigger_algo/_common/_explain.py:143`, `imusician.py:251`,
`admin_service_pricing.py:52`. Neuf fois le même geste recopié, neuf fois sans clé
de route, donc neuf culs-de-sac.

Ce module est l'endroit unique. Il ne connaît aucune source : il reçoit une entrée
du registre et la rend.

Ce que le corpus impose
------------------------
Yifrah, *Microcopy* p.129 : « au lieu de dire qu'il n'y a rien ici, écris ce qui est
censé s'y trouver ou ce qu'on peut y faire […] si c'est pertinent, ajoute les
instructions, ou fournis un lien. » C'est la structure exacte du rendu ci-dessous :
**ce que ça apporte**, puis **le geste**, puis **le bouton**.

p.138 : « n'écris jamais à tes utilisateurs à propos du système ». Les raisons brutes
vivent dans `etl_run_log.error_message` et se lisent « no SoundCloud user_id and no
claimed track » ; ce module ne les voit jamais. C'est structurel, pas une consigne :
il n'a accès qu'au registre, où les textes sont écrits pour un humain.

⚠️ Ce qu'il ne fait PAS
------------------------
Il ne décide pas QUAND s'afficher. Une source peut être légitimement silencieuse —
Meta sans campagne active, S4A sans sortie depuis le dernier import — et lui demander
un geste serait l'alerte toujours rouge qui a crié 85 nuits d'affilée. Le tri des
états vit chez l'appelant ; ce module rend ce qu'on lui donne.
"""
from __future__ import annotations

from typing import Callable

import streamlit as st

from src.dashboard.utils.i18n import t
from src.dashboard.utils.navigation import goto
from src.database.stripe_schema import page_is_locked


def _texte(valeur: str | Callable[[], str]) -> str:
    """Le registre porte des APPELABLES, pour que `t()` tourne au rendu.

    Une chaîne figée à l'import garderait la langue du premier visiteur pour tout
    le processus — même raison que `setup_completion._Declared.label`.
    """
    return valeur() if callable(valeur) else str(valeur)


def render_absence(source: dict, *, plan: str, key: str) -> None:
    """Ce qui devrait être là, ce que ça apporte, et LE bouton qui y mène.

    `source` est une entrée de `SOURCES_CONFIG` : elle porte `icon`, `label`,
    `valeur`, `geste` et `page`.

    ⚠️ Le bouton mène à `upgrade` quand la page est fermée au plan, jamais à une
    page vide. C'est la doctrine déjà appliquée au raccourci PDF de l'accueil et au
    bouton de rendez-vous : un bouton qui promet et ouvre un mur est pire qu'un
    bouton absent.
    """
    page = source["page"]
    verrouille = page_is_locked(plan, page)

    st.markdown(
        f"**{source['icon']} {source['label']}** — "
        + t("absence.manque", "il te manque {valeur}").format(
            valeur=_texte(source["valeur"])))
    st.caption(_texte(source["geste"]))

    libelle = (t("absence.cta_verrouille", "🔒 Inclus dans Premium")
               if verrouille else
               t("absence.cta", "Y aller →"))
    if st.button(libelle, key=f"absence_{key}", width="stretch"):
        goto("upgrade" if verrouille else page)


def render_absence_list(sources: list[dict], *, plan: str,
                        limite: int = 3, prefixe: str = "") -> None:
    """Les sources manquantes, les plus utiles d'abord, et le reste replié.

    ⚠️ `limite` existe parce qu'un écran de dix gestes ne se lit pas : un locataire
    neuf n'a RIEN de branché, et lui présenter dix boutons équivalents revient à ne
    lui en présenter aucun. Trois tiennent dans un premier écran et se hiérarchisent
    — le registre porte `poids` pour ça.

    Le reste n'est pas caché : il est replié. Ce sont deux choses différentes, et
    c'est la seule manière de respecter à la fois Yifrah p.129 (« dis ce qu'on peut
    faire ici ») et Few p.97 (le premier écran porte ce qui compte, pas tout).
    """
    if not sources:
        return
    ordonnees = sorted(sources, key=lambda s: -s.get("poids", 0))
    for src in ordonnees[:limite]:
        render_absence(src, plan=plan, key=f"{prefixe}{src['label']}")

    reste = ordonnees[limite:]
    if not reste:
        return
    titre = t("absence.reste", "Et {n} autre(s) source(s) à brancher").format(
        n=len(reste))
    with st.expander(titre, expanded=False):
        for src in reste:
            render_absence(src, plan=plan, key=f"{prefixe}{src['label']}")
