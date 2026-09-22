"""Une différence entre deux mesures espacées n'est pas un quotidien.

Type: Test
Uses: ast, la base joignable
Depends on: src/dashboard/views/apple_music.py,
            src/dashboard/utils/pdf_exporter/_collectors.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
`plays - LAG(plays) OVER (ORDER BY date)` suppose deux mesures **consécutives**. Apple
Music est nourri par un dépôt de CSV à la main, donc les mesures sont espacées. Mesuré
le 2026-09-20 sur `apple_songs_history` :

    11 paires · **0 consécutive** · plus grand trou **12 jours**

**Cent pour cent des points** portaient donc la croissance de plusieurs jours posée sur
une seule journée. Un artiste lisait un pic là où il y avait une accumulation.

⚠️ **Les DEUX lecteurs, pas un.** La vue et le moteur PDF portaient la même requête ;
corriger l'un aurait laissé l'autre mentir, et c'est la classe que ce dépôt a déjà payée
avec `canonical_song_sql`.

⚠️ La différence non consécutive est **écartée**, pas mise à zéro : la taire serait
inventer un zéro, la dessiner serait inventer un pic. Son absence se voit — c'est la
règle « l'absence devient un pixel ».
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_LECTEURS = (
    "src/dashboard/views/apple_music.py",
    "src/dashboard/utils/pdf_exporter/_collectors.py",
)


def _literaux(rel: str) -> list[str]:
    """Les chaînes du module, docstrings exclues — la LISTE, pas le blob recousu."""
    return _sql_du_fichier(rel).split("\x00")


def _sql_du_fichier(rel: str) -> str:
    """Le SQL que ce fichier CONTIENT, lu dans ses littéraux — pas dans son texte.

    ⚠️ La première version de ce garde comparait des expressions régulières au TEXTE du
    fichier, et `test_a_guard_reads_structure_not_text` l'a refusée. Elle avait raison :
    **quatre gardes ont été pris au vert sur le défaut qu'ils existaient pour attraper,
    en une seule soirée**, parce qu'un commentaire ou une docstring suffisait à satisfaire
    la correspondance. Ici le commentaire qui EXPLIQUE le correctif contient
    `jours_ecoules = 1` — il aurait tenu le garde à lui seul.

    Passer par `ast` règle le problème par construction : un commentaire n'est pas un
    nœud, et une docstring est écartée explicitement.
    """
    arbre = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    # ⚠️ PAR `id()`, ET C'EST UNE CORRECTION — 2026-09-21.
    #
    # La version d'avant faisait `docs = {ast.get_docstring(n) …}` puis
    # `if n.value not in docs`. `ast.get_docstring()` rend la docstring NETTOYÉE
    # (dédentée, `.strip()`), quand `n.value` est le littéral BRUT : dès qu'une
    # docstring commence par un retour à la ligne ou porte une indentation — donc
    # presque toujours — les deux chaînes diffèrent et l'exclusion ne s'applique
    # pas. La docstring entrait dans le « SQL du fichier ».
    #
    # Mesuré ce jour-là : la docstring de `views/apple_music.py`, qui EXPLIQUE que
    # la table morte n'est plus lue, suffisait à faire croire au garde qu'elle
    # l'était encore. C'est exactement le défaut que ce fichier se vantait d'avoir
    # réglé « par construction » — il l'avait réglé pour les commentaires, pas pour
    # les docstrings.
    docs = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corps = getattr(n, "body", None)
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                docs.add(id(corps[0].value))
    morceaux = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if id(n) not in docs:
                morceaux.append(n.value)
        elif isinstance(n, ast.JoinedStr):
            morceaux.extend(v.value for v in n.values
                            if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return "\x00".join(morceaux)


@pytest.mark.parametrize("rel", _LECTEURS)
def test_a_span_difference_is_never_presented_as_a_daily_figure(rel: str) -> None:
    """LE GARDE, et sa PROPRIÉTÉ a changé le 2026-09-21 — pas son intention.

    L'intention reste celle du 2026-09-20 : une différence entre deux mesures
    espacées n'est pas un quotidien, et la présenter comme tel fait lire un pic
    là où il y a une accumulation.

    ⚠️ **LE REMÈDE, LUI, ÉTAIT FAUX, et ce fichier portait la mesure qui le
    prouve.** Il exigeait `jours = 1`, c'est-à-dire deux relevés consécutifs. Sa
    propre docstring mesurait : « 11 paires · **0 consécutive** ». Un filtre qui
    écarte CENT POUR CENT de sa population n'assainit pas une figure, il
    l'éteint — et c'est ce que l'artiste a vu : une section vide. Apple se dépose
    à la main ; deux relevés consécutifs n'existent pas dans ce produit.

    La propriété gardée est donc : **si une surface expose un GAIN entre deux
    relevés Apple, elle expose aussi la DURÉE sur laquelle il a été gagné.** Deux
    façons de la tenir, les deux acceptées :

      · contraindre à des jours consécutifs (`jours = 1`) — le gain EST alors
        quotidien ;
      · porter l'écart (`days_since_previous` / `jours_ecoules`) jusqu'à
        l'écran — le gain est alors qualifié.

    C'est `a-sweep-predicate-that-matches-a-form-not-a-property`, règle 20 de
    CLAUDE.md : le prédicat encodait UN remède quand la classe parle d'une
    propriété.
    """
    # ⚠️ ON NE REGARDE QUE LES LITTÉRAUX SQL, et c'est une correction attrapée
    # par mutation le 2026-09-21. Le premier jet cherchait « jours » dans TOUTES
    # les chaînes du fichier : la légende française « … sur %{customdata} jour(s) »
    # le satisfaisait, donc retirer la colonne du SELECT laissait le garde VERT.
    # Un prédicat qui accepte de la prose à la place d'une colonne ne garde rien.
    # ⚠️ ON FILTRE LES LITTÉRAUX, PAS LES LIGNES — seconde correction du même
    # jour. Découper le blob sur `\n` coupait les requêtes multi-lignes en deux :
    # aucune ligne ne portait à la fois SELECT et FROM, la liste sortait vide, et
    # les deux cas partaient en `skip`. Un garde qui skippe ne garde rien, et il
    # le fait sans rougir — c'est pire qu'un garde absent, parce qu'on le compte.
    requetes = [c for c in _literaux(rel)
                if "SELECT" in c.upper() and "FROM" in c.upper()]
    sql = "\n".join(requetes)
    gain = re.search(r"LAG\s*\(\s*plays", sql) or "daily_plays" in sql
    if not gain:
        pytest.skip(f"{rel} n'expose plus de gain Apple entre deux relevés")

    consecutif = re.search(r"(jours_ecoules|jours)\s*=\s*1", sql)
    duree = re.search(r"\b(days_since_previous|jours_ecoules)\b", sql)
    assert consecutif or duree, (
        f"{rel} expose un gain entre deux relevés Apple sans porter la DURÉE sur "
        "laquelle il a été gagné. Mesuré le 2026-09-21 : l'écart entre deux "
        "relevés va de 12 à 179 jours chez le locataire 1 — un gain de 36 écoutes "
        "sur 179 jours n'est pas comparable à un gain de 36 sur 12.\n"
        "Deux remèdes acceptés : contraindre à `jours = 1`, ou porter "
        "`days_since_previous` jusqu'à l'écran.")


def test_the_surface_actually_shows_the_span() -> None:
    """Porter la durée dans le SQL ne suffit pas : l'artiste doit la LIRE.

    Sans ce second test, le précédent serait satisfait par une colonne
    sélectionnée et jamais affichée — « a-guard-that-sees-the-binding-not-the-
    application », la classe que ce dépôt a nommée sur son propre cliquet de
    fenêtres.
    """
    vue = ROOT / "src" / "dashboard" / "views" / "apple_music.py"
    arbre = ast.parse(vue.read_text(encoding="utf-8"))
    docs = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corps = getattr(n, "body", None)
            if corps and isinstance(corps[0], ast.Expr) \
                    and isinstance(corps[0].value, ast.Constant) \
                    and isinstance(corps[0].value.value, str):
                docs.add(id(corps[0].value))
    # La durée doit apparaître dans un texte DESTINÉ À L'ÉCRAN — une étiquette,
    # un survol ou une légende — pas seulement dans la requête.
    affiche = [n.value for n in ast.walk(arbre)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docs
               and ("jour" in n.value.lower() or " j" in n.value)
               and "SELECT" not in n.value.upper()]
    assert affiche, (
        "la vue Apple ne dit nulle part à l'écran sur COMBIEN de jours un gain a "
        "été accumulé. La colonne peut être lue et jetée : c'est le trou que ce "
        "test existe pour fermer.")


def test_the_data_still_justifies_the_guard() -> None:
    """ANTI-VACUITÉ, et la mesure rejouée plutôt que recopiée.

    Si Apple redevenait quotidien, la contrainte n'écarterait plus rien et ce garde
    deviendrait décoratif. Ce test le dirait — c'est le moment de rouvrir la question
    « faut-il encore écarter ? » plutôt que de la laisser figée.
    """
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable")
    try:
        r = db.fetch_query(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE d = 1), MAX(d) FROM ("
            "  SELECT date - LAG(date) OVER (PARTITION BY song_name ORDER BY date) d"
            "    FROM apple_songs_history) t WHERE d IS NOT NULL")[0]
    finally:
        db.close()
    paires, consecutives, trou = r
    if paires == 0:
        pytest.skip("aucune paire sur cette instance")
    assert consecutives < paires, (
        f"les {paires} paires sont TOUTES consécutives (plus grand trou : {trou} j). "
        "Apple est redevenu quotidien : la contrainte `jours = 1` n'écarte plus rien, "
        "et la question « faut-il encore écarter ? » mérite d'être rouverte.")
