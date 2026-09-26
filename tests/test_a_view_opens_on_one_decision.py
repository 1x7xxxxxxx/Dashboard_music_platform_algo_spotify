"""
Guard — une vue n'ouvre pas sur un mur de graphiques.

Type: Sub
Uses: ast, pathlib
Triggers: pytest
Depends on: src/dashboard/views/**, src/dashboard/utils/ui.py
Persists in: nothing

Error class: too-many-charts-competing-for-one-decision.

Remonté par un artiste en test le 2026-08-12 : « réduire le nombre de graphs qui
permettent de prendre décision ». Le correctif — `ui.secondary_analyses()`, un dépliant
qui applique « une décision par écran » — a été écrit **le jour même**, avec la remarque
citée dans son propre commentaire de module.

Onze jours plus tard il était appliqué sur quatre sites, et sur **aucune** des cinq vues
les plus denses :

    Road to Algo  15 graphiques + jusqu'à 17 jauges ≈ 35 figures
    Data Wrapped   9
    Créatives      8
    Meta Ads       8
    Prévisions     6

Le correctif existait, le diagnostic était juste, et la distance entre les deux n'était
mesurée nulle part. Ce garde la mesure.

Ce qu'il compte : les graphiques rendus **au premier écran**, c'est-à-dire hors d'un
`with secondary_analyses(...)` et hors d'un `st.expander(...)`. Rien n'interdit d'en avoir
beaucoup — il faut seulement qu'ils ne soient pas tous dépliés d'emblée.
"""

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_VIEWS = _ROOT / "src" / "dashboard" / "views"
_RENDERERS = {"plotly_chart", "altair_chart", "line_chart", "bar_chart",
              "area_chart", "pyplot"}
# Plafond du PREMIER ÉCRAN. Few (*Information Dashboard Design*) : un tableau de bord
# tient dans un coup d'œil. Cinq laisse de la marge tout en interdisant le mur.
_MAX_FIRST_SCREEN = 5

#: Les vues dont le premier écran porte DÉLIBÉRÉMENT plus que le plafond général.
#:
#: ⚠️ UNE EXEMPTION QUI SE VÉRIFIE, et pas une liste de noms. Ce dépôt a vidé une
#: exemption codée en dur le matin du 2026-09-22 (`audit_runner.non_concluants`) parce
#: qu'elle avait survécu à sa raison, et le remède posé ce jour-là est le même ici :
#: `test_every_raised_ceiling_is_still_needed` rougit dès qu'une entrée cesse d'être
#: nécessaire. On ne peut donc pas laisser derrière soi un plafond relevé pour rien.
#:
#: `spotify_s4a_combined` : six figures, trois questions posées deux par deux et lues
#: côte à côte — sorties/audience, puis ce-qui-bouge/détail. Son bloc « Analyses
#: détaillées » est PERMANENT depuis le 2026-09-22 (un `st.expander` reste refermable,
#: et on voulait qu'il ne le soit pas), donc ses trois figures sont honnêtement des
#: figures de premier écran. Elles l'étaient déjà depuis le 2026-09-21 sans que ce
#: garde puisse le voir : il abritait le bloc par son NOM, pas par son état.
#: VIDE au 2026-09-22 au soir, et la façon dont elle s'est vidée est le point.
#:
#: Elle a porté `spotify_s4a_combined` à 6 pendant quelques heures : le bloc
#: « Analyses détaillées » était devenu permanent, donc ses trois figures étaient
#: honnêtement des figures de premier écran. Puis deux de ces figures ont FUSIONNÉ
#: — sauvegardes, playlists et abonnés sur une seule, avec un axe secondaire — et la
#: page est repassée à 5, le plafond général.
#:
#: `test_every_raised_ceiling_is_still_needed` l'a dit le jour même : « son exemption
#: n'a plus d'objet et masquerait une régression jusqu'à 6 ». C'est exactement ce que ce
#: garde existe pour attraper, et il l'a fait sur l'exemption de son propre auteur, six
#: heures après sa pose. Une exemption qu'on doit se rappeler de retirer ne se retire
#: jamais.
_PLAFOND_PAR_VUE: dict[str, int] = {}


def _view_files() -> list[str]:
    out = []
    for p in sorted(_VIEWS.rglob("*.py")):
        if "__pycache__" in str(p) or p.name.startswith("__"):
            continue
        out.append(str(p.relative_to(_ROOT)))
    return out


def _tab_names(tree: ast.Module) -> set[str]:
    """Les variables issues d'un `st.tabs([...])` — `a, b, c = st.tabs([...])`."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        if getattr(node.value.func, "attr", "") != "tabs":
            continue
        for cible in node.targets:
            if isinstance(cible, ast.Name):
                out.add(cible.id)
            elif isinstance(cible, ast.Tuple):
                out |= {e.id for e in cible.elts if isinstance(e, ast.Name)}
    return out


def _collapsed_lines(tree: ast.Module) -> set[int]:
    """Lignes vivant dans un dépliant — `secondary_analyses`, `expander` ou un ONGLET."""
    covered = set()
    onglets = _tab_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        names = {
            (getattr(i.context_expr.func, "id", "")
             or getattr(i.context_expr.func, "attr", ""))
            for i in node.items if isinstance(i.context_expr, ast.Call)
        }
        # `with tab_impact:` — le contexte est une VARIABLE, pas un appel.
        if any(isinstance(i.context_expr, ast.Name) and i.context_expr.id in onglets
               for i in node.items):
            names = names | {"tabs"}
        # ⚠️ `tabs` EST RECONNU DEPUIS LE 2026-09-21, et c'est une correction, pas
        # un assouplissement. Le MESSAGE de ce garde promet déjà la sortie —
        # « ou déplacer dans un onglet — un onglet BORNE un écran » — et le
        # prédicat ne l'implémentait pas. La promesse était écrite, elle n'était
        # pas tenue : une vue qui suivait le conseil restait accusée.
        #
        # C'est la même forme que le Dockerfile refusé par
        # `test_a_guard_reads_structure_not_text` alors que son message annonçait
        # l'exemption. Un garde dont le remède ne passe pas son propre contrôle
        # pousse à contourner le contrôle.
        #
        # Un onglet borne bien un écran : `st.tabs` n'en affiche qu'un à la fois.
        # Il ne borne PAS le coût — Streamlit exécute tous les corps — mais ce
        # garde-ci compte ce qui S'AFFICHE, pas ce qui s'exécute.
        if names & {"secondary_analyses", "expander", "tabs"}:
            for stmt in node.body:
                covered |= set(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
    return covered


def _first_screen_charts(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    collapsed = _collapsed_lines(tree)
    return sorted(
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", "") in _RENDERERS
        and n.lineno not in collapsed
    )


def test_the_scan_is_not_vacuous():
    """NON-VACUITÉ. Ajoutée le 2026-09-12.

    Le cliquet est paramétré sur une liste de vues. Une liste vide ne produit
    AUCUN cas de test — pytest n'échoue pas, il n'exécute rien — et le plafond de
    cinq éléments de premier écran certifie alors une propriété sur zéro page.

    Mutation record — 2026-09-12 : avec `_VIEWS` réduit à `[]`, le cliquet ne
    produit plus aucun cas et reste « vert » ; ce test rougit en nommant la liste.
    """
    scanned = _view_files()
    assert len(scanned) >= 20, (
        f"{len(scanned)} vue(s) balayée(s) — il y en avait 44 le 2026-09-12. Un "
        "cliquet paramétré sur une liste vide n'exécute rien et ne rougit jamais.")


def test_the_tool_still_exists():
    ui = (_ROOT / "src" / "dashboard" / "utils" / "ui.py").read_text(encoding="utf-8")
    assert "def secondary_analyses" in ui, (
        "`secondary_analyses` a disparu — c'est le seul motif de dépliage que ce garde "
        "reconnaît, et il a été écrit pour cette remarque précise."
    )


@pytest.mark.parametrize("rel", _view_files())
def test_a_view_does_not_open_on_a_wall_of_charts(rel: str):
    lines = _first_screen_charts(_ROOT / rel)
    plafond = _PLAFOND_PAR_VUE.get(rel, _MAX_FIRST_SCREEN)
    assert len(lines) <= plafond, (
        f"{rel} rend {len(lines)} graphiques au PREMIER ÉCRAN (lignes {lines[:8]}…). "
        f"Plafond : {plafond}. Replie les graphiques qui RAFFINENT une "
        f"décision sans la faire :\n"
        f"    with secondary_analyses():\n"
        f"        st.plotly_chart(fig_detail, width=\"stretch\")\n"
        f"Rien n'est supprimé — tout reste à un clic."
    )


@pytest.mark.parametrize("rel", sorted(_PLAFOND_PAR_VUE))
def test_every_raised_ceiling_is_still_needed(rel: str):
    """UNE EXEMPTION SE VÉRIFIE. Un plafond relevé pour rien est un garde désarmé.

    Trois façons dont une entrée de `_PLAFOND_PAR_VUE` peut cesser d'avoir un objet,
    et les trois sont refusées ici :

      * le fichier a disparu ;
      * la vue est repassée SOUS le plafond général — l'entrée n'exempte plus rien et
        masquerait une future régression jusqu'à son propre chiffre ;
      * le plafond de l'entrée est plus BAS que le plafond général, ce qui n'est pas
        une exemption mais une confusion.

    Ce garde est le remède posé le matin du 2026-09-22, quand une exemption codée en
    dur dans `audit_runner.non_concluants` a survécu aux deux classes qu'elle
    exemptait : la liste serait restée, et un futur balayage muet y serait passé en
    silence.
    """
    chemin = _ROOT / rel
    assert chemin.is_file(), (
        f"« {rel} » a un plafond relevé et n'existe plus : retirer l'entrée de "
        "`_PLAFOND_PAR_VUE`.")
    plafond = _PLAFOND_PAR_VUE[rel]
    assert plafond > _MAX_FIRST_SCREEN, (
        f"le plafond de « {rel} » ({plafond}) n'est pas plus haut que le plafond "
        f"général ({_MAX_FIRST_SCREEN}) : ce n'est pas une exemption.")
    n = len(_first_screen_charts(chemin))
    assert n > _MAX_FIRST_SCREEN, (
        f"« {rel} » ne rend plus que {n} graphiques au premier écran, sous le plafond "
        f"général de {_MAX_FIRST_SCREEN} : son exemption n'a plus d'objet et masquerait "
        f"une régression jusqu'à {plafond}. La retirer.")


def test_the_detector_sees_the_defect_it_is_written_for(tmp_path):
    """Non-vacuity on a FABRICATED view: charts on the first screen are counted, the
    ones folded under `secondary_analyses` are not."""
    view = tmp_path / "wall.py"
    view.write_text("import streamlit as st\n"
                    "st.plotly_chart(a)\nst.plotly_chart(b)\nst.bar_chart(c)\n"
                    "with secondary_analyses('Détail'):\n"
                    "    st.plotly_chart(d)\n    st.plotly_chart(e)\n", encoding="utf-8")
    assert len(_first_screen_charts(view)) == 3
