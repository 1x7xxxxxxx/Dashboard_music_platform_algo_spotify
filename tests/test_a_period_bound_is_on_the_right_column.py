"""Une fenêtre appliquée ne suffit pas — elle doit porter sur la bonne date.

Type: Test
Uses: pytest, ast
Depends on: src/utils/clocks.py, src/dashboard/views/
Persists in: nothing

Le trou que ce fichier ferme (2026-09-10)
-----------------------------------------
Un garde posé le matin vérifie que toute requête sous un sélecteur reprend sa fenêtre.
Il ne dit rien de **sur quoi** elle porte, et j'avais écrit que ce jugement n'était pas
mécanisable. C'était faux, et l'inventaire l'a montré : **13 sites de bornage, six
colonnes distinctes, dont UNE SEULE est une date de publication.**

Le cas qui a fait naître ce garde : Instagram bornait « Engagement par mois » sur
`timestamp`, la date de PUBLICATION du post, alors que `like_count` est un compteur
cumulé lu aujourd'hui. La barre de janvier portait les likes donnés en juin à un post
de janvier. La fenêtre était appliquée — sur la mauvaise chose — et tous les gardes
existants passaient au vert, parce qu'ils demandaient *que* la fenêtre soit appliquée,
jamais *sur quoi*.

Ce que ce garde exige
---------------------
Il n'interdit pas de borner sur une date de sortie : c'est un regroupement légitime, et
souvent le seul possible — Instagram ne nous donne qu'un compteur courant par post, il
n'existe aucun flux mensuel à calculer. Ce qu'il exige, c'est que la figure le DISE.
« Likes acquis à ce jour, par mois de publication » et « Engagement par mois » ne
décrivent pas la même chose, et seul le second se lit comme un flux.

Le sujet de chaque colonne est déclaré une fois, dans `src/utils/clocks.py`, à côté de
l'horloge qui l'a produite — deux questions différentes sur la même colonne, et il
fallait les deux.
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

from src.utils.clocks import COLUMN_SUBJECT, Dates, is_cohort_column, subject_of

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

_MAKERS = {"smart_period_filter", "period_filter", "entity_period_filter"}

# Les PHRASES qui annoncent une lecture par cohorte. Des mots isolés ne suffisent pas,
# et c'est mesuré : la première version cherchait « publication », que la page
# Instagram contient sept fois dans des titres de section sans rapport (« 📸
# Publications », « Publié le »). Un garde satisfait par le vocabulaire du domaine ne
# garde rien. Une annonce nomme le REGROUPEMENT, pas le sujet de la page.
_COHORT_PHRASES = (
    "par mois de publication", "par date de publication", "par date de sortie",
    "acquis à ce jour", "cohorte de publication", "cohorte de sortie",
    "by month of publication", "by publication date", "earned to date",
)

# Combien de lignes après le bornage on considère comme « autour de la figure ».
# Au-delà, le texte parle d'autre chose sur la même page.
_NEARBY_LINES = 90


@lru_cache(maxsize=32)
def _user_facing_strings(rel: str, start: int = 0, end: int = 10 ** 6) -> tuple[str, ...]:
    """Les chaînes que l'artiste LIT, entre deux lignes : `t()`, titres, légendes.

    Un commentaire ou un docstring n'annonce rien à personne — seul ce qui atteint
    l'écran le peut. Et la fenêtre de lignes compte : sur une page Instagram, le mot
    « publications » vit dans sept titres de section sans rapport avec la figure.
    """
    tree = ast.parse((VIEWS / rel).read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if not (start <= getattr(node, "lineno", 0) <= end):
            continue
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "t":
            # `t("clé", "défaut")` — le défaut est le texte français affiché.
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.append(arg.value)
        elif name in ("caption", "header", "subheader", "markdown", "info",
                      "warning", "write", "title"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out.append(arg.value)
        for kw in node.keywords:
            if kw.arg in ("title", "labels", "yaxis_title", "xaxis_title"):
                for c in ast.walk(kw.value):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        out.append(c.value)
    return tuple(out)


@lru_cache(maxsize=1)
def _bindings() -> list[tuple[str, str, int]]:
    """(fichier, colonne bornée, ligne) pour chaque sélecteur de période."""
    out = []
    for path in sorted(VIEWS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            cols: list[str] = []
            if name in _MAKERS:
                for kw in node.keywords:
                    if kw.arg == "date_column" and isinstance(kw.value, ast.Constant):
                        cols.append(kw.value.value)
                # `EntitySpec(table, entity, date_column, …)` — 3ᵉ position.
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    if (isinstance(arg, ast.Call)
                            and getattr(arg.func, "id", None) == "EntitySpec"
                            and len(arg.args) >= 3
                            and isinstance(arg.args[2], ast.Constant)):
                        cols.append(arg.args[2].value)
            elif name == "sql_between" and node.args:
                if isinstance(node.args[0], ast.Constant):
                    cols.append(node.args[0].value)
            for c in cols:
                out.append((str(path.relative_to(VIEWS)), c, node.lineno))
    return out


def test_every_bound_column_declares_what_it_dates() -> None:
    """Une colonne dont on ignore le sujet ne peut pas être jugée."""
    undeclared = sorted({c for _f, c, _ln in _bindings() if subject_of(c) is None})
    assert not undeclared, (
        f"ces colonnes bornent une figure sans que `COLUMN_SUBJECT` dise de quoi elles "
        f"sont la date : {undeclared}. Tant qu'on l'ignore, on ne peut pas dire si la "
        "figure répond à ce qu'elle annonce — c'est le trou par lequel « Engagement "
        "par mois » est passé.")


def test_a_cohort_bound_figure_says_so() -> None:
    """Borner sur une date de SORTIE est légitime — le taire ne l'est pas."""
    offenders = []
    for f, col, lineno in _bindings():
        if not is_cohort_column(col):
            continue
        # Dans un texte VU PAR L'ARTISTE, pas n'importe où dans le fichier.
        #
        # La première version cherchait le mot dans tout le source : un commentaire
        # expliquant le correctif suffisait alors à satisfaire le garde, et une
        # mutation qui retirait l'annonce de l'ÉCRAN restait verte. C'est la même
        # faiblesse que « une mention vaut un bornage », trouvée le même jour — et
        # c'est la sixième fois que ce dépôt mesure qu'un garde textuel se satisfait
        # de sa propre documentation.
        near = _user_facing_strings(f, lineno, lineno + _NEARBY_LINES)
        if not any(w in txt.lower() for txt in near for w in _COHORT_PHRASES):
            offenders.append(f"{f}:{lineno} borne sur `{col}`")
    assert not offenders, (
        f"{offenders} : la fenêtre porte sur une date de PUBLICATION, donc la figure "
        "regroupe par cohorte de sortie et non par période d'activité. C'est une "
        "lecture valable — souvent la seule possible — mais elle doit être annoncée. "
        "« Engagement par mois » se lit comme un flux ; « likes acquis à ce jour, par "
        "mois de publication » dit ce qui est réellement montré.")


def test_the_inventory_is_not_empty() -> None:
    """Non-vacuité : sans sites, les deux contrôles ci-dessus sont vrais de rien."""
    b = _bindings()
    assert len(b) >= 10, (
        f"seulement {len(b)} bornage(s) trouvé(s) — il y en avait 13 le 2026-09-10. "
        "L'extraction vise à côté, et les deux contrôles passent sur du vide.")
    assert {c for _f, c, _ln in b} >= {"date", "collected_at", "timestamp"}, (
        "les trois familles de colonne — événement, mesure, publication — ne sont plus "
        "toutes représentées ; le garde ne prouve plus qu'il sait les distinguer.")


def test_the_three_subjects_are_actually_distinguished() -> None:
    """Un prédicat qui rendrait tout `event` satisferait le contrôle sans rien voir."""
    kinds = set(COLUMN_SUBJECT.values())
    assert kinds == {Dates.EVENT, Dates.MEASUREMENT, Dates.PUBLICATION}, (
        f"les trois sujets ne sont plus tous déclarés : {sorted(kinds)}")
    assert _COHORT_PHRASES and all(" " in p for p in _COHORT_PHRASES), (
        "les annonces de cohorte sont redevenues des MOTS isolés. « publication » "
        "apparaît sept fois sur la page Instagram dans des titres sans rapport : un "
        "garde satisfait par le vocabulaire du domaine ne garde rien.")
    assert is_cohort_column("timestamp") and not is_cohort_column("date"), (
        "la distinction publication / événement s'est effondrée — c'est elle, et elle "
        "seule, qui distingue une cohorte d'un flux")


# ── Un écran de FRAÎCHEUR lit la date de la DONNÉE — 2026-09-18 ──────────────
#
# Les tests ci-dessus portent sur les figures BORNÉES par une période. Un écran de
# supervision n'est pas borné : il demande `MAX(<colonne>)` et affiche le résultat comme
# « dernière donnée ». C'est la même question — de quelle horloge parle-t-on — et aucun
# garde ne la posait là.
#
# Mesuré le 2026-09-18 : `_supervision_freshness` (`views/admin.py`) interroge sept
# tables. Six lisent la date métier. La septième lisait `MAX(collected_at)::date FROM
# apple_songs_history`, **la seule des sept à porter aussi une colonne `date`**. Écart du
# jour : 0. Le défaut était LATENT — et c'est exactement pour ça qu'il a survécu à un
# correctif qui avait déjà traité ses deux voisines de liste.
#
# La preuve que la classe mord vraiment est ailleurs, dans la même base :
# `meta_insights_performance_day` porte `MAX(collected_at)` = aujourd'hui et
# `MAX(day_date)` = 2024-09-30 — **718 jours**. `src/utils/freshness_monitor.py:18` le
# documente, et `src/utils/quality_gate.py:40-41` écrit la règle.
#
# ⚠️ Ce garde a besoin de la BASE : « cette table a-t-elle une date métier ? » ne se lit
# pas dans le code. Il saute sans Postgres, comme ses pairs — et son test de population
# refuse de passer en silence sur un inventaire vide.
_ADMIN = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views" / "admin.py"
_FRAICHEUR = re.compile(r'"SELECT MAX\((?P<col>[a-z_]+)\)(?:::date)? FROM (?P<tbl>[a-z_0-9]+)"')
# Une date de MESURE (quand on a écrit) contre une date de SUJET (ce que la donnée date).
_ECRITURE = {"collected_at", "created_at", "updated_at", "inserted_at", "fetched_at"}


def _lectures_de_fraicheur() -> list[tuple[int, str, str]]:
    """`(ligne, colonne, table)` pour chaque `MAX(...)` de l'écran de supervision."""
    texte = _ADMIN.read_text(encoding="utf-8")
    return [(texte[:m.start()].count("\n") + 1, m.group("col"), m.group("tbl"))
            for m in _FRAICHEUR.finditer(texte)]


def test_the_freshness_screen_was_really_found() -> None:
    """Non-vacuité : sans extraction, le test ci-dessous est vert pour rien."""
    lues = _lectures_de_fraicheur()
    assert len(lues) >= 5, (
        f"seulement {len(lues)} requête(s) de fraîcheur extraite(s) de admin.py — "
        "l'écran a changé de forme et le garde ne lit plus rien.")


def test_a_freshness_screen_reads_the_date_the_data_carries() -> None:
    """Quand la table porte une date métier, l'écran de fraîcheur la lit."""
    import os
    import socket
    psycopg2 = __import__("pytest").importorskip("psycopg2")
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", 5433))
    except OSError:
        __import__("pytest").skip("Postgres 5433 injoignable — « cette table a-t-elle "
                                  "une date métier ? » ne se lit pas dans le code")
    finally:
        s.close()
    conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="spotify_etl",
                            user="postgres", password=os.getenv("DB_PASSWORD", "postgres"),
                            connect_timeout=3)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND (data_type LIKE '%date%' OR data_type LIKE '%timestamp%')
            """)
            par_table: dict[str, set[str]] = {}
            for t, c in cur.fetchall():
                par_table.setdefault(t, set()).add(c)
    finally:
        conn.close()

    fautifs = []
    for ligne, col, tbl in _lectures_de_fraicheur():
        if col not in _ECRITURE:
            continue
        metier = sorted(par_table.get(tbl, set()) - _ECRITURE)
        # `track_created_at` date le TITRE, pas la mesure — ce n'est pas une date de
        # relevé, et la lire ferait dire à l'écran une autre chose encore.
        metier = [m for m in metier if not m.endswith("_created_at")]
        if metier:
            fautifs.append((ligne, tbl, col, metier))
    assert not fautifs, (
        "".join(f"\n  admin.py:{ln} lit `MAX({c})` sur `{t}`, qui porte {m}"
                for ln, t, c, m in fautifs) +
        "\n\nCet écran annonce « last-data date » : il doit lire la date PORTÉE PAR LA "
        "DONNÉE quand elle existe, jamais sa date d'écriture (`quality_gate.py:40-41`). "
        "Sur `meta_insights_performance_day`, confondre les deux vaut **718 jours** "
        "(`freshness_monitor.py:18`). Sur Apple l'écart valait 0 le 2026-09-18 — un "
        "défaut latent survit à un correctif qui a traité ses voisines.")
