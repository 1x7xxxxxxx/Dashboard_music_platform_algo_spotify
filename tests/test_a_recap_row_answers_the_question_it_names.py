"""Le récapitulatif de l'accueil : une colonne, une question, un chiffre stable.

Type: Test
Uses: pytest, platform_chart.render_platform_chart, home._recap_metrics
Depends on: src/dashboard/utils/platform_chart_notes.py, src/dashboard/views/home.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Le tableau à droite de la figure a gagné des lignes DÉRIVÉES le 2026-09-12 — meilleur
pas, coût par écoute, meilleur CPR, probabilité de déclenchement. Trois défauts sont
apparus **au rendu, pas à la lecture du code**, et aucun test existant ne pouvait les
voir :

1. **Le coût par écoute changeait avec le MODE D'AFFICHAGE** — 0,0170 € en « Par
   période », 0,0101 € en « Cumulé », même période, même dépense. Basculer un mode ne
   change pas ce qu'une écoute a coûté : le dénominateur était la série DESSINÉE, et
   la somme des écarts quotidiens d'un compteur sous-compte (facteur 887 mesuré le
   2026-09-11). Corrigé en lisant `platform_totals`, qui prend la différence de
   niveau.
2. **« 📈 Meilleure semaine 286 346 · 01/06/26 » en mode cumulé** — une série cumulée
   ne fait que monter, donc son maximum est toujours son DERNIER point. Le chiffre
   était le niveau final et la date la fin de la fenêtre : deux façons de ne rien
   dire, présentées comme un pic. Un commentaire annonçait déjà que « la ligne
   saute » ; rien ne la faisait sauter.
3. **La bannière et la ligne Total affichaient 308 060 et 304 793** côte à côte, sans
   qu'un mot distingue leurs portées — l'écart valant exactement les écoutes Apple,
   qui ne sont pas traçables hors du pas annuel. C'est la contradiction pour laquelle
   les tuiles avaient été RETIRÉES le 2026-09-10 ; la remettre en place en les
   rendant aurait rejoué la même séance.

La question commune : **une ligne répond-elle à la question que son libellé pose ?**
Un nombre juste sous un mauvais libellé est plus coûteux qu'un nombre absent.

Journal de mutation — 2026-09-12, chacune vue rouge avec son message :
  * dénominateur remis sur la série dessinée → le cas 1 nomme les deux coûts ;
  * garde `mode != "cumulative"` retiré → le cas 2 nomme la ligne et sa valeur ;
  * « Total tracé » renommé « Total » → le cas 3 nomme les deux nombres.
"""
from __future__ import annotations

import datetime as _d
from unittest.mock import patch

import pytest

from src.dashboard.utils import platform_chart as pc
from src.dashboard.views.home import _recap_extra, _recap_metrics

_DAYS = [_d.date(2025, 1, 1) + _d.timedelta(days=i) for i in range(200)]

# Un COMPTEUR dont la collecte a des trous : c'est là que la somme des écarts et la
# différence de niveau divergent, donc la seule mise en scène où le défaut 1 existe.
_SERIES = {
    "spotify": [(x, 100) for x in _DAYS],
    "youtube": [(x, 50) for x in _DAYS[::7]],       # un jour sur sept seulement
}
# `platform_totals` rendrait la DIFFÉRENCE DE NIVEAU ; on la pose à la main pour que
# le test ne dépende d'aucune base. 20 000 est volontairement loin de la somme des
# écarts dessinés — sans cet écart, le cas 1 ne pourrait pas rougir.
_TOTALS = {"spotify": 20_000, "youtube": 20_000}
_SIDE = {"meta_spend": 400.0, "ig_delta": -5,
         "best_cpr": 0.0112, "best_cpr_name": "CONKRETE", "best_cpr_spend": 18.41,
         "best_algo_p": 0.118, "best_algo_name": "Radio", "best_algo_song": "X"}


class _Slot:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _table(mode: str, step: str = "month", prev_total=None) -> str:
    """Rend la figure et retourne la table markdown du récapitulatif."""
    out: list = []
    with patch("streamlit.plotly_chart", lambda f, **k: None), \
         patch("streamlit.caption", lambda *a, **k: None), \
         patch("streamlit.info", lambda *a, **k: None), \
         patch("streamlit.markdown", lambda v, **k: out.append(str(v))):
        drawn = pc.render_platform_chart(
            _SERIES, since=_DAYS[0], until=_DAYS[-1], step=step, mode=mode,
            recap=_Slot(), recap_extra=_recap_extra(_TOTALS, _SIDE),
            recap_metrics=lambda al, sp, gr, st_, md: _recap_metrics(
                _SIDE, _TOTALS, al, sp, st_, md, prev_total=prev_total),
            key=f"recap_{mode}_{step}_{prev_total}")
    assert drawn, f"la figure ne s'est pas rendue en mode {mode}"
    tbl = next((x for x in out if x.startswith("|")), None)
    assert tbl, f"aucune table markdown rendue en mode {mode} — le garde est aveugle"
    return tbl


def _row(tbl: str, needle: str) -> str | None:
    """La ligne de CORPS qui porte `needle` — jamais l'en-tête ni le séparateur.

    Les deux premières versions de ce fichier ont rougi sur leurs propres aiguilles :
    « Meilleur » attrapait « Meilleur CPR », et « Total » attrapait l'en-tête
    `| Plateforme | Total |`. Un garde qui échoue sur sa mise en scène plutôt que sur
    son sujet est pire qu'absent : on relâche l'assertion jusqu'à ce qu'il se taise.
    """
    body = tbl.split("\n")[2:]
    return next((r for r in body if needle in r), None)


def test_the_cost_per_stream_does_not_depend_on_the_display_mode():
    """Basculer « Cumulé » ↔ « Par période » ne change pas ce qu'une écoute a coûté."""
    seen = {}
    for mode in ("absolute", "cumulative", "share"):
        row = _row(_table(mode), "Coût par écoute")
        assert row, f"la ligne « coût par écoute » a disparu en mode {mode}"
        seen[mode] = row.split("|")[2].strip()
    assert len(set(seen.values())) == 1, (
        "le coût par écoute change avec le MODE D'AFFICHAGE : "
        + " · ".join(f"{k}={v}" for k, v in seen.items())
        + ". Le dénominateur est reparti sur la série dessinée ; la somme des écarts "
          "quotidiens d'un compteur sous-compte (facteur 887 mesuré le 2026-09-11). "
          "Il doit venir de `platform_totals`, qui lit la différence de niveau.")


def test_a_cumulative_series_has_no_best_step():
    """Le maximum d'une série qui ne fait que monter est son dernier point."""
    tbl = _table("cumulative")
    row = _row(tbl, "📈")
    assert row is None, (
        f"le récapitulatif annonce un pic en mode cumulé : « {row.strip()} ». Une "
        "série cumulée ne redescend jamais, donc ce « meilleur » est le niveau final "
        "et sa date la fin de la fenêtre — deux façons de ne rien dire, présentées "
        "comme un pic.")


def test_a_period_series_does_have_one():
    """NON-VACUITÉ : sans ce sens, supprimer la ligne rendrait le test ci-dessus vert."""
    row = _row(_table("absolute"), "📈")
    assert row, (
        "aucune ligne « meilleur pas » en mode « Par période », où elle a un sens : "
        "le test du mode cumulé passerait alors en ne mesurant rien.")


def test_the_drawn_total_says_that_it_is_drawn():
    """Deux totaux justes côte à côte, dont un plus petit, se distinguent par un mot."""
    tbl = _table("absolute")
    row = _row(tbl, "**")
    assert row and "tracé" in row, (
        f"la ligne de total ne nomme pas sa portée : « {(row or '').strip()} ». La "
        "bannière au-dessus de la figure porte TOUTES les plateformes de la période "
        "(Apple comprise) ; cette ligne ne somme que ce que la figure DESSINE. "
        "Mesuré à l'écran le 2026-09-12 : 308 060 contre 304 793, l'écart valant les "
        "3 267 écoutes Apple listées deux lignes plus bas. C'est la contradiction "
        "pour laquelle les tuiles avaient été retirées le 2026-09-10.")


def test_a_predicted_probability_is_never_called_an_observed_rate():
    """`s4a_song_algo_outcomes` porte 0 ligne : aucun taux observé n'existe.

    Mesuré le 2026-09-12, tous locataires confondus. Ce qui est affiché est la sortie
    du modèle ; l'appeler « taux de déclenchement » inventerait une mesure que
    personne n'a prise.
    """
    row = _row(_table("absolute"), "%")
    assert row, "la ligne de probabilité a disparu du récapitulatif"
    low = row.lower()
    assert "prédite" in low or "prédit" in low, (
        f"« {row.strip()} » ne dit pas que le chiffre est PRÉDIT. Le taux observé "
        "demanderait `s4a_song_algo_outcomes`, à 0 ligne : le mot est la seule chose "
        "qui sépare une prédiction d'une mesure.")
    assert "taux" not in low, (
        f"« {row.strip()} » annonce un TAUX. Un taux se constate ; ceci se calcule.")


@pytest.mark.parametrize("gone", ["Mesurés", "Unité"])
def test_the_columns_the_reader_could_not_name_are_gone(gone):
    """« À quoi correspond la colonne mesurés ? » — une colonne qu'on doit expliquer.

    Elle disait `171 / 181`, le nombre de pas renseignés. L'information est vraie, et
    la hachure de la figure la porte déjà là où le trou se trouve. L'unité, elle,
    coûtait une colonne entière pour trois lignes — elle est passée dans le libellé.
    """
    tbl = _table("absolute")
    header = tbl.split("\n")[0]
    assert gone not in header, (
        f"la colonne « {gone} » est revenue dans l'en-tête : {header.strip()}")
    assert header.count("|") == 3, (
        f"le tableau n'a plus deux colonnes : {header.strip()}. Une table large "
        "repousse la figure, et c'est elle qu'on regarde.")


# ── LES TROIS MÉTRIQUES AJOUTÉES LE 2026-09-12 ───────────────────────────────
#
# Chacune ouvre un piège précis, et chacun a déjà été payé sous une autre forme
# dans ce même fichier : une règle juste pour un régime, fausse pour un autre.
#
# Journal de mutation — chacune vue ROUGE avant que le garde soit gardé :
#   * `mode not in ("share", "cumulative")` réduit à `mode != "cumulative"`
#     → test_the_dominant_platform_is_absent_where_it_would_be_a_share_of_a_share
#       ÉCHOUE en nommant le mode et la valeur affichée ;
#   * `if prev_total and now_total` réduit à `if prev_total is not None`
#     → test_no_growth_is_claimed_against_an_unmeasured_period ÉCHOUE ;
#   * plancher `seen < len(span)` retiré → test_measured_periods_only_speaks_when_
#     the_window_has_holes ÉCHOUE en nommant « 200 / 200 ».


def test_the_dominant_platform_is_absent_where_it_would_be_a_share_of_a_share():
    """En mode « Part », `aligned` porte déjà des pourcentages.

    En tirer une part donnerait la part d'une part — un nombre qui ressemble à une
    réponse. En mode « Cumulé », les valeurs sont des NIVEAUX : leur somme n'est pas
    un total de période, donc le rapport non plus. La ligne ne doit exister que là où
    elle a un sens, et son absence ailleurs est la garantie.
    """
    row = _row(_table("absolute"), "Plateforme dominante")
    assert row, (
        "la ligne « Plateforme dominante » a disparu du mode où elle est JUSTE — "
        "un garde de régime qui interdit tous les régimes ne garde rien")

    for mode in ("share", "cumulative"):
        bad = _row(_table(mode), "Plateforme dominante")
        assert bad is None, (
            f"« Plateforme dominante » s'affiche en mode {mode} : {bad!r}. En "
            "« Part » c'est la part d'une part ; en « Cumulé » c'est un rapport de "
            "niveaux, pas de quantités. Même famille que le meilleur pas, qui "
            "affichait le dernier point d'une courbe cumulée comme un pic.")


def test_no_growth_is_claimed_against_an_unmeasured_period():
    """Sans période précédente MESURÉE, aucune variation n'est affichée."""
    for prev in (None, 0):
        tbl = _table("absolute", prev_total=prev)
        assert _row(tbl, "période précédente") is None, (
            f"une variation s'affiche contre une période précédente à {prev!r}. Un "
            "« +100 % » contre une fenêtre jamais collectée transforme le début de "
            "NOTRE observation en croissance de l'artiste — le mensonge le plus "
            "facile de ce tableau.")
        # ⚠️ ET LE BLOC DOIT AVOIR TOURNÉ. Sans cette seconde assertion, le garde
        # passe pour la mauvaise raison, mesuré le 2026-09-12 : `prev_total=0` avec
        # un prédicat `is not None` lève une division par zéro, que le `try/except`
        # de `render_platform_chart` avale (« recap metrics unavailable »). TOUTES
        # les métriques disparaissent alors, « période précédente » comprise, et
        # l'absence attendue est produite par l'effondrement au lieu du garde.
        #
        # C'est la classe `a-guard-satisfied-by-the-collapse-it-should-catch` : le
        # harnais ment, pas le prédicat. On exige donc qu'une AUTRE métrique du même
        # bloc soit là — preuve que le bloc s'est exécuté jusqu'au bout.
        assert _row(tbl, "Coût par écoute"), (
            f"avec prev_total={prev!r}, AUCUNE métrique ne s'affiche : le bloc a "
            "levé et `render_platform_chart` a avalé l'exception. L'absence de "
            "« période précédente » ne prouve alors rien — elle est un symptôme de "
            "la panne, pas l'effet du garde.")

    row = _row(_table("absolute", prev_total=10_000), "période précédente")
    assert row, (
        "aucune variation affichée alors que la période précédente vaut 10 000 : "
        "le garde ci-dessus ne prouve plus rien, il passerait sur une ligne morte")
    # `_TOTALS` somme 40 000 : +300 % exactement. Un signe inversé est la faute que
    # ce chiffre rend visible, et elle ne se verrait pas sur un écart proche de zéro.
    assert "+300,0 %" in row, (
        f"la variation ne vaut pas +300,0 % contre 10 000 pour 40 000 : {row!r}")


def test_measured_periods_only_speaks_when_the_window_has_holes():
    """« 200 / 200 » ne dit rien — la ligne ne s'affiche que si elle informe."""
    # Au pas MOIS sur 200 jours, YouTube est collecté un jour sur sept : les seaux
    # existent tous, donc aucun trou et aucune ligne.
    full = _row(_table("absolute", step="month"), "Périodes mesurées")
    if full is not None:
        head, val = full.split("|")[1].strip(), full.split("|")[2].strip()
        a, _, b = val.partition(" / ")
        assert a != b.split()[0], (
            f"« {head} » affiche {val} : une fenêtre sans trou ne mérite pas de "
            "ligne. Elle occupe une place que le lecteur relit à chaque rendu pour "
            "y trouver la même absence d'information.")
