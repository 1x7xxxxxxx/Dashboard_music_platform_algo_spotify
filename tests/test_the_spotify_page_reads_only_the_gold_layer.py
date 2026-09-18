"""La page Spotify ne lit que la couche or, et ses règles ne s'oublient plus.

Type: Test
Uses: ast
Triggers: CI, select_tests.py
Depends on: rien (aucune base, aucun réseau)

Ce que ce fichier garde, et pourquoi c'est structurel
-----------------------------------------------------
`s4a_song_timeline` porte DEUX règles que chaque requête devait se rappeler : retirer
la ligne « Total » des CSV (`song NOT ILIKE '%1x7xxxxxxx%'`, règle transverse #8) et
dédupliquer par (date, titre). Une règle qu'il faut se rappeler est une règle qu'on
oublie : la page en avait trois lectures brutes au 2026-09-14.

`v_s4a_song_daily` (migration 105) porte les deux. Tant que la page ne lit QUE des
vues or, la question ne se pose plus — c'est le seul correctif qui survit à la
prochaine personne qui écrira une requête ici.

Le test lit l'AST, pas le texte : un nom de table cité dans un commentaire ou une
docstring n'est pas une lecture. Le dépôt a pris quatre gardes textuels verts sur
leur propre défaut.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "src" / "dashboard" / "views" / "spotify_s4a_combined.py"

# Les tables de FAIT que cette page n'a plus le droit de lire : chacune porte une
# règle qu'une vue or applique déjà.
_BRONZE = {
    "s4a_song_timeline": "v_s4a_song_daily",
    "s4a_audience": "v_s4a_audience_daily / v_s4a_audience_monthly",
    "s4a_songs_global": "— (instantané par fenêtre : deux âges dans une même table)",
    "tracks": "v_s4a_release_cohort (rattachement par lien confirmé)",
    "artist_history": "v_spotify_followers_daily",
}


def _sql_literals(path: pathlib.Path) -> list[str]:
    """Toute chaîne du module, docstrings EXCLUES — y compris les f-strings recousues."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))

    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            # Une f-string : on recoud ses morceaux littéraux, les trous restent des trous.
            out.append("".join(
                v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)))
    return out


def _reads(text: str, table: str) -> bool:
    return re.search(rf"\b(?:FROM|JOIN)\s+{re.escape(table)}\b", text, re.I) is not None


def test_the_page_reads_no_bronze_table():
    offenders = []
    for lit in _sql_literals(PAGE):
        for table, replacement in _BRONZE.items():
            if _reads(lit, table):
                offenders.append(f"{table} (→ {replacement}) dans : {' '.join(lit.split())[:90]}")
    assert not offenders, (
        "La page Spotify lit une table de bronze. Chacune porte une règle qu'une vue "
        "or applique déjà — la lire directement, c'est réécrire la règle et la voir "
        "diverger.\n  " + "\n  ".join(offenders))


def _joins_on_a_display_name(sql: str) -> bool:
    """Cette requête rapproche-t-elle un titre par son NOM d'affichage ?

    Extrait du corps du test pour être appelable : tant qu'il y vivait, la seule
    façon de savoir s'il mordait encore était d'écrire le défaut dans la vraie page.
    `assert not offenders` est vert sur une page propre ET sur un prédicat aveugle.
    """
    return bool(
        re.search(r"REPLACE\s*\(\s*\w*\.?track_name", sql, re.I)
        or re.search(r"track_name\s*\)?\s*=\s*\w*\.?song\b", sql, re.I)
        or re.search(r"\btrr\.title\s*=\s*\w*\.?song\b", sql, re.I)
    )


def test_the_detector_sees_the_join_it_is_written_for():
    """Non-vacuité : les trois formes interdites sont FABRIQUÉES ici.

    Chacune est celle qui a réellement perdu 95 686 écoutes sur 163 088 ; la forme
    corrigée — le passage par `track_platform_link` — doit rester muette, sans quoi
    corriger le défaut rendrait la CI rouge.
    """
    for interdit in (
        "SELECT * FROM t JOIN trr ON REPLACE(trr.track_name, '_', ' ') = s.song",
        "SELECT * FROM t JOIN trr ON trr.track_name = s.song",
        "SELECT * FROM t JOIN trr ON trr.title = s.song",
    ):
        assert _joins_on_a_display_name(interdit), (
            f"forme interdite non détectée : {interdit}. Le rapprochement par nom "
            "d'affichage repasserait sans un mot, et il perd les titres dont le nom "
            "de fichier CSV diffère du vrai titre.")

    correct = ("SELECT * FROM t JOIN track_platform_link l "
               "ON l.platform_title = s.song AND l.platform = 's4a' "
               "AND l.status = 'confirmed'")
    assert not _joins_on_a_display_name(correct), (
        "le détecteur accuse le rattachement CORRIGÉ par `track_platform_link` : "
        "corriger deviendrait impossible sans désarmer le garde.")


def test_the_page_does_not_join_a_display_name_to_a_song():
    """Le défaut mesuré : la jointure par nom perdait 59 % des écoutes.

    `track_release_reference.title` porte le « ? » du vrai titre ; `song` porte un
    « _ », parce que le nom vient du NOM DE FICHIER du CSV. Joindre les deux perdait
    5 titres sur 11 et 95 686 écoutes sur 163 088 — dont le plus gros du catalogue.
    """
    offenders = [" ".join(lit.split())[:100]
                 for lit in _sql_literals(PAGE) if _joins_on_a_display_name(lit)]
    assert not offenders, (
        "Rapprochement par NOM d'affichage. Le rattachement passe par "
        "`track_platform_link` (platform='s4a', status='confirmed'), dont "
        "`platform_title` porte le nom S4A exact.\n  " + "\n  ".join(offenders))


# --- non-vacuité -----------------------------------------------------------------

def test_the_detector_sees_a_bronze_read_when_there_is_one():
    """Sans ça, le test passerait aussi sur un fichier vide."""
    assert _reads("SELECT x FROM s4a_song_timeline WHERE y", "s4a_song_timeline")
    assert _reads("... JOIN tracks tk ON ...", "tracks")


def test_the_detector_ignores_a_table_named_in_prose():
    """Un nom de table dans un commentaire ou une docstring n'est pas une lecture."""
    src = (
        'def f():\n'
        '    """On ne lit plus FROM s4a_song_timeline ici."""\n'
        '    # ni FROM tracks\n'
        '    return "SELECT day FROM v_s4a_song_daily"\n'
    )
    tmp = ROOT / "tests" / "_tmp_prose_probe.py"
    tmp.write_text(src, encoding="utf-8")
    try:
        lits = _sql_literals(tmp)
        assert not any(_reads(lit, "s4a_song_timeline") for lit in lits), lits
        assert not any(_reads(lit, "tracks") for lit in lits), lits
    finally:
        tmp.unlink()


def test_the_page_actually_reads_the_gold_views():
    """Un fichier qui ne lit RIEN passerait les deux tests ci-dessus."""
    lits = _sql_literals(PAGE)
    for view in ("v_s4a_song_daily", "v_s4a_audience_monthly",
                 "v_s4a_song_measured_span", "v_s4a_release_reach",
                 "v_s4a_release_cohort", "v_spotify_followers_daily"):
        assert any(_reads(lit, view) for lit in lits), f"{view} n'est lue nulle part"


@pytest.mark.parametrize("table", sorted(_BRONZE))
def test_every_bronze_table_has_a_named_replacement(table):
    """Une interdiction sans remplacement nommé se fait contourner."""
    assert _BRONZE[table].strip(), table


# --- les clés construites dynamiquement ont toutes leur libellé -------------------

# Les sources que `v_spotify_followers_daily` (migration 120) peut rendre. Le
# préfixe `spotify_s4a_combined.source.` est exempté du détecteur d'orphelines
# (`test_i18n_orphans`) parce que la clé est bâtie en f-string ; cette liste est ce
# qui empêche l'exemption d'ouvrir une porte sans contrôle.
_FOLLOWER_SOURCES = ("s4a_csv", "spotify_api")


@pytest.mark.parametrize("source", _FOLLOWER_SOURCES)
def test_every_follower_source_is_named(source):
    import sys
    sys.path.insert(0, str(ROOT))
    from src.dashboard.utils.i18n_catalog.spotify_s4a_combined import EN
    key = f"spotify_s4a_combined.source.{source}"
    assert key in EN, (
        f"la source '{source}' s'affichera avec sa clé brute en anglais — "
        f"ajoute '{key}' au catalogue")


def test_the_migration_still_declares_exactly_these_sources():
    """Si la migration gagne une source, ce test rougit AVANT l'écran."""
    sql = (ROOT / "migrations" / "120_gold_spotify_followers.sql").read_text(encoding="utf-8")
    declared = set(re.findall(r"'([a-z0-9_]+)'::text\s+AS\s+source|'([a-z0-9_]+)'::text\s*$",
                              sql, re.M))
    found = {a or b for a, b in declared} - {""}
    assert set(_FOLLOWER_SOURCES) <= found, (
        f"la migration 120 déclare {sorted(found)}, la liste du test "
        f"{sorted(_FOLLOWER_SOURCES)} — elles ont divergé")


# --- une série ne commence pas avant que la chose existe --------------------------

def test_the_detail_series_starts_at_the_first_stream():
    """Spotify exporte la timeline du COMPTE, zéros compris, avant la sortie.

    Mesuré le 2026-09-14 : **6 365 lignes** à `streams = 0` antérieures à la sortie
    du titre. « Ô Chiotte l'arbitre Tucome Back », sorti le 30/08/2024, en porte
    **20 mois**. Le zéro est réel dans le fichier — le parseur n'invente rien — et
    FAUX à l'écran : « le titre n'existait pas » n'est pas « personne ne l'a écouté ».
    La série de détail doit donc partir de `first_streamed`, jamais du premier jour
    du fichier.
    """
    # Par l'AST, jamais par le texte : `"first_streamed" in source` serait satisfait
    # par le commentaire qui EXPLIQUE le correctif. Le méta-garde du dépôt refuse
    # cette forme, et il a raison — trois gardes ont été pris verts sur leur propre
    # commentaire le 2026-09-04. La question est : quel NOM le code lit-il vraiment ?
    tree = ast.parse(PAGE.read_text(encoding="utf-8"))
    read_names = {
        n.slice.value for n in ast.walk(tree)
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
        and isinstance(n.slice.value, str)
    }
    assert "first_streamed" in read_names, (
        "la page ne lit plus la colonne `first_streamed` : la courbe de détail "
        "repartira du premier jour du fichier, donc de mois de plat à zéro pour un "
        "titre qui n'était pas publié. Colonnes lues : "
        f"{sorted(read_names)}")
    detail = [lit for lit in _sql_literals(PAGE)
              if _reads(lit, "v_s4a_song_daily") and "song = %s" in lit]
    assert detail, "la requête de détail par titre est introuvable"
    assert any("day >= %s" in lit for lit in detail), (
        "la requête de détail ne porte plus de borne de départ — elle tracera les "
        "zéros antérieurs à la sortie")


# --- la vue d'horizon ne se relit pas elle-même ------------------------------------

def test_the_reach_view_scans_the_cohort_once():
    """Le défaut de PERFORMANCE mesuré, et sa cause.

    La première version détectait les trous par « îlots » (day_index − ROW_NUMBER),
    ce qui obligeait à référencer la cohorte DEUX fois puis à les auto-joindre. Le
    planificateur estime **1 ligne** là où la cohorte en rend 9 335 — le filtre de
    jointure lui est opaque — choisit donc une boucle imbriquée et réexécute tout le
    sous-plan par ligne : **plus de 2 minutes**, quand la cohorte seule tourne en
    51 ms. Une seule passe de `LAG` répond à la même question ; la page rend en 75 ms.

    Classe `a-subplan-re-executed-by-a-misestimated-row-count`. Le garde est
    structurel plutôt que chronométré : une mesure de temps est instable, une double
    référence ne l'est pas.
    """
    sql = (ROOT / "migrations" / "119_gold_s4a_release_cohort.sql").read_text(encoding="utf-8")
    reach = sql[sql.index("CREATE OR REPLACE VIEW v_s4a_release_reach"):]
    refs = len(re.findall(r"\bFROM\s+v_s4a_release_cohort\b", reach, re.I))
    assert refs <= 1, (
        f"`v_s4a_release_reach` référence la cohorte {refs} fois. Une seconde "
        f"référence force le planificateur à recalculer tout le sous-plan — c'est "
        f"le passage de 75 ms à plus de 2 minutes, mesuré le 2026-09-14.")
    # ⚠️ `"MATERIALIZED" in sql` — la forme d'avant le 2026-09-18 — était VERTE sur le
    # commentaire de la ligne 57, qui contient le mot. Défaut reinstauré en entier
    # (`WITH linked AS MATERIALIZED (` → `WITH linked AS (`, migration 119 ligne 61) :
    # les 16 tests restaient verts. C'est `guard-matches-its-own-comment` retourné —
    # le garde n'était pas rouge sur sa prose, il était SATISFAIT par elle.
    sans_prose = re.sub(r"--[^\n]*", "", sql)
    assert re.search(r"\bWITH\s+linked\s+AS\s+MATERIALIZED\b", sans_prose, re.I), (
        "la CTE `linked` n'est plus matérialisée : inlinée, elle laisse appliquer le "
        "filtre de correspondance APRÈS la jointure aux 13 794 lignes quotidiennes "
        "— 142 399 lignes produites puis jetées (mesuré par EXPLAIN ANALYZE).")


def test_the_cohort_starts_at_the_release_and_not_before() -> None:
    """Un jour ANTÉRIEUR à la sortie entre dans la cohorte comme un zéro mesuré.

    Ajouté le 2026-09-18, et c'est la raison qui compte : la classe
    `a-zero-that-predates-the-thing-it-measures` nommait ce fichier comme son garde,
    et **aucune de ses assertions ne portait sur cette borne**. Toutes couvraient
    `a-subplan-re-executed-by-a-misestimated-row-count` — même migration, même vue,
    autre défaut. Un `guard:` qui pointe le bon FICHIER ne prouve pas que la classe
    soit gardée ; il faut ouvrir les assertions.

    Le défaut, lui, est silencieux par construction : sans la borne, chaque jour où
    `s4a_song_timeline` porte une ligne pour un titre pas encore sorti devient un
    « 0 écoute à J-12 ». La courbe de cohorte démarre plus bas, la pente paraît plus
    forte, et rien n'échoue.
    """
    sql = (ROOT / "migrations" / "119_gold_s4a_release_cohort.sql").read_text(encoding="utf-8")
    cohorte = sql[sql.index("CREATE OR REPLACE VIEW v_s4a_release_cohort"):]
    cohorte = cohorte[:cohorte.index(";", cohorte.index("SELECT")) + 1] \
        if ";" in cohorte else cohorte
    # Commentaires retirés : le fichier porte `-- `day >= release_date` ancre la
    # cohorte…` en ligne 44. La tranche commence après, donc le garde ne s'y trompe
    # pas AUJOURD'HUI — mais un commentaire déplacé DANS la vue le rendrait vert sur
    # sa propre prose, ce qui vient d'arriver à l'assertion `MATERIALIZED` juste
    # au-dessus. On ne laisse pas la correction dépendre d'un ordre de lignes.
    assert re.search(r"\bday\s*>=\s*\w*\.?release_date\b",
                     re.sub(r"--[^\n]*", "", cohorte), re.I), (
        "`v_s4a_release_cohort` ne borne plus ses jours à la date de sortie. Les "
        "jours ANTÉRIEURS entrent alors dans la cohorte avec 0 écoute — un zéro qui "
        "précède la chose qu'il mesure. La courbe démarre plus bas et la pente "
        "paraît plus forte, sans qu'aucune ligne ne soit fausse prise isolément.")
