"""Guard — an artist-facing view opens on at most N decision charts.

Beta feedback (Grinch, 2026-08-12): "réduire le nombre de graphs qui permettent
de prendre décision". The charts were not wrong; too many of them competed for
the same decision, so none of them drove one. The rule adopted:

    a chart is PRIMARY if, alone, it can change what the artist does next;
    everything that only refines that answer goes inside `secondary_analyses()`,
    collapsed, one click away — deleted from the first screen, not from the code.

This test counts `st.plotly_chart` calls that are NOT nested in a
`secondary_analyses()` block, per view, and fails when a view exceeds its
budget. Adding a chart to a full view is then a deliberate act: either it earns
PRIMARY (raise the budget here, on purpose) or it goes in the expander.
"""
import ast
from pathlib import Path

import pytest

_VIEWS = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"

# Views an artist lands on to decide something, and their first-paint budget.
# Budgets are the CURRENT counts after the 2026-08-20 pass — they are a ratchet:
# lower them freely, raise one only with a reason written in the diff.
_BUDGET = {
    "instagram.py": 2,             # followers trend + engagement per month
    # 1 → 3 le 2026-09-21, DÉLIBÉRÉMENT, et voici les trois décisions distinctes.
    # Ce cliquet demande une raison écrite dans le diff pour toute hausse ; la
    # voici, parce que « j'ai ajouté des figures » n'en est pas une.
    #
    #   · le CATALOGUE dans le temps (écoutes, likes, reposts, commentaires) —
    #     demandé par le propriétaire le 2026-09-21, et il n'existait nulle part :
    #     la page ne savait montrer qu'un TITRE à la fois ;
    #   · la croissance d'un TITRE choisi — la figure historique, qui répond à
    #     « celui-ci décolle-t-il ? », une autre question ;
    #   · le CLASSEMENT, qui était un tableau de sept colonnes et devient deux
    #     cadres : volume et taux d'engagement. Ce n'est pas une figure de plus,
    #     c'est un tableau qui devient lisible — le taux d'engagement y est la
    #     vraie information, et un tri par volume l'enterrait.
    #
    # La base 100 reste ABRITÉE dans `secondary_analyses` : elle compare des
    # métriques entre elles et n'ouvre aucune action.
    "soundcloud.py": 3,
    "youtube.py": 2,               # channel trend + top content
    # ⚠️ 3 → 6 le 2026-09-22, DÉLIBÉRÉMENT, et le chiffre d'avant était un angle mort
    # que le code annonçait déjà. Le bloc « 📊 Analyses détaillées » était un
    # `secondary_analyses(expanded=True)` depuis le 2026-09-21 : OUVERT à l'écran, donc
    # ses trois figures étaient peintes au premier coup d'œil, et ce garde les abritait
    # quand même parce qu'il reconnaît le bloc par son NOM et non par son état. Le
    # commentaire de la vue le disait mot pour mot : « cette page peint donc SIX
    # figures au premier écran là où ils en comptent trois ».
    #
    # Le 2026-09-22 le tiroir est devenu un bandeau PERMANENT — demandé en regardant
    # l'écran, parce qu'un `st.expander` reste refermable et qu'un clic malheureux
    # cachait le détail. Le nom disparaît, l'abri avec, et le compte devient vrai.
    #
    # Ce n'est donc PAS un desserrage : c'est le plafond qui rattrape la réalité. Les
    # six figures répondent à trois questions posées deux par deux, côte à côte :
    # sorties/audience, puis ce-qui-bouge/détail.
    # 6 → 5 le même soir : deux figures du bandeau ont fusionné (sauvegardes,
    # playlists et abonnés sur une seule, les abonnés sur un axe secondaire). Un
    # budget qu'on laisse au-dessus de la mesure est du crédit pour une régression.
    # 5 → 3 le 2026-09-26 : le verdict de la pub est parti vers `meta_x_spotify` (R195),
    # et le détail du titre et l'engagement ne font plus qu'UNE figure à deux panneaux
    # (R194). Descendu à la mesure, pour que le plafond reste serré.
    "spotify_s4a_combined.py": 3,
    "apple_music.py": 2,
    "imusician.py": 2,
    # 1 → 3 le 2026-09-21, DÉLIBÉRÉMENT, et les trois répondent à trois questions
    # distinctes — chacune dans SON onglet, donc jamais trois à l'écran.
    #
    #   📈 l'impact dans le temps — la figure historique ;
    #   🔽 le parcours Meta × Spotify × Hypeddit, RAPATRIÉ de « Publicité Meta
    #      Ads » et corrigé : `lp_views` et `custom_conversions` y étaient empilés
    #      comme deux étapes successives alors que ce sont deux MESURES de la même
    #      étape, la première sous-comptant — `lp < conv` **91 jours sur 91** ;
    #   🌍 le croisement PAYS : dépense Meta × écoutes du distributeur. C'est lui
    #      qui rend visible 0,002 €/écoute en Colombie contre 0,181 € au Brésil,
    #      **93×**, que ni la page Meta ni la page Spotify ne pouvaient dire.
    # 3 → 4 le 2026-09-26, DÉLIBÉRÉMENT (R195) : « Ta dernière pub t'a-t-elle amené des
    # auditeurs ? » est arrivée en tête de page depuis la page Spotify, à la demande du
    # propriétaire — la figure déménage, elle ne s'ajoute pas (Spotify descend de 5 à 3).
    "meta_x_spotify.py": 4,
}


def _primary_chart_count(path: Path) -> int:
    """st.plotly_chart calls not enclosed in a secondary_analyses() block."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    shielded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        if not any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "id", None) == "secondary_analyses"
            for item in node.items
        ):
            continue
        for inner in ast.walk(node):
            shielded.add(id(inner))

    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "plotly_chart"
        and id(node) not in shielded
    )


@pytest.mark.parametrize("filename,budget", sorted(_BUDGET.items()))
def test_view_opens_on_at_most_its_chart_budget(filename, budget):
    path = _VIEWS / filename
    assert path.exists(), f"{filename} listed in the budget but missing"
    count = _primary_chart_count(path)
    assert count <= budget, (
        f"{filename} paints {count} charts on open (budget {budget}). Either move "
        f"the refining ones into `with secondary_analyses(...)`, or raise the "
        f"budget here deliberately."
    )


def test_the_counter_still_sees_charts_and_every_budgeted_file_exists():
    """NON-VACUITÉ. Ajoutée le 2026-09-12.

    `count <= budget` est vrai quand le compteur rend zéro — ce qu'il ferait si
    `st.plotly_chart` était renommé, si un fichier budgété disparaissait, ou si
    `_primary_chart_count` cessait de parser. Les trois laisseraient les sept
    plafonds au vert en ne mesurant plus rien.

    Mutation record — 2026-09-12 : en retirant `"soundcloud.py"` du disque (copie
    déplacée), ce test le nomme ; en faisant rendre 0 à `_primary_chart_count`, il
    rougit sur le total. Le cliquet lui-même reste vert dans les deux cas, ce qui
    est précisément la raison d'être de celui-ci.
    """
    total = 0
    for name in _BUDGET:
        path = _VIEWS / name
        assert path.is_file(), (
            f"{name} est budgété mais n'existe plus sous {_VIEWS.name}/. Son plafond "
            "ne mesure plus rien et reste vert pour cette raison.")
        total += _primary_chart_count(path)
    assert total >= 8, (
        f"{total} figure(s) de premier écran vues sur les {len(_BUDGET)} fichiers "
        "budgétés — il y en avait 13 le 2026-09-12. Le compteur est devenu aveugle, "
        "et sept plafonds certifient alors une propriété qu'ils ne vérifient plus.")


def test_secondary_analyses_actually_shields_charts(tmp_path):
    """The counter must respond to the mechanism, or the budget means nothing."""
    src = (
        "import streamlit as st\n"
        "from src.dashboard.utils.ui import secondary_analyses\n"
        "st.plotly_chart(a)\n"
        "with secondary_analyses('x'):\n"
        "    st.plotly_chart(b)\n"
        "    st.plotly_chart(c)\n"
    )
    tmp = tmp_path / "_chart_budget_probe.py"  # tmp_path, never the real tree: a probe written there races the tree's scanners under xdist (2026-09-26)
    tmp.write_text(src, encoding="utf-8")
    try:
        assert _primary_chart_count(tmp) == 1
    finally:
        tmp.unlink()


def test_instagram_kept_its_charts_only_moved_them():
    """Réduction = relocalisation, jamais suppression — SAUF décision du propriétaire.

    ⚠️ 4 → 3 le 2026-09-21, et c'est la PREMIÈRE suppression assumée depuis que ce
    test existe. Elle mérite d'être écrite plutôt que de faire baisser un nombre.

    La figure supprimée est « Évolution relative (base 100) ». Demande littérale :
    « SUPPRIMER LE GRAPHIQUE BASE 100, SI ON ARRIVE TOUT METTRE MAIS PAS EN BASE
    100 ». Elle existait pour une raison réelle — abonnés (1 522), abonnements
    (621) et publications (51) sont dans un rapport de 30, donc illisibles sur un
    repère commun — mais elle payait ce service avec les CHIFFRES : on y lisait
    « 103 » au lieu de « 1 525 abonnés ».

    Les trois séries vivent maintenant dans UNE figure en petits multiples, avec
    leurs vraies valeurs. La figure « Évolution des Abonnés » seule disparaît donc
    aussi : elle en était le premier cadre, dessiné deux fois.

    Bilan : 4 figures → 3, dont une SUPPRIMÉE et deux FUSIONNÉES. Le compte de
    premier écran passe de 2 à 2 — la fusion ne coûte rien à l'écran d'ouverture.
    """
    text = (_VIEWS / "instagram.py").read_text(encoding="utf-8")
    assert text.count("st.plotly_chart") == 3
    assert _primary_chart_count(_VIEWS / "instagram.py") == 2
